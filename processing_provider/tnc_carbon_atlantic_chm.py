__author__ = 'Vitor Di Lorenzzi Nunes da Cunha'
__date__ = '2025-09-25'
__copyright__ = '(C) 2025 by Vitor Di Lorenzzi Nunes da Cunha'

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication # type: ignore
from qgis.core import (QgsProcessingAlgorithm, # type: ignore
                       QgsWkbTypes,
                       QgsRasterLayer,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterRasterDestination,
                       QgsProcessingParameterFileDestination,
                       NULL)

from osgeo import gdal, osr # type: ignore
import processing # type: ignore
import numpy as np
import csv

class TNC_Carbon_Atlantic_CHM(QgsProcessingAlgorithm):
    INPUT_RASTER = 'INPUT_RASTER'
    INPUT_POLYGON = 'INPUT_POLYGON'
    INPUT_CANOPY_COVER_THRESHOLD = 'INPUT_CANOPY_COVER_THRESHOLD'
    OUTPUT_RASTER = 'OUTPUT_RASTER'
    OUTPUT_CSV = 'OUTPUT_CSV'


    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_RASTER,
                self.tr('Canopy height model raster layer (CHM)')
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_POLYGON,
                self.tr('Polygon layer'),
                [QgsWkbTypes.PolygonGeometry],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_CANOPY_COVER_THRESHOLD, 
                self.tr('Canopy cover threshold (default = 2.0m)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=2.0,
                optional=False
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_RASTER, 
                self.tr('Output raster layer'),
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_CSV,
                self.tr('Output CSV file'),
                'CSV files (*.csv)'
            )
        )



    def processAlgorithm(self, parameters, context, feedback):
        # Receber camada de entrada e o caminho para a camada de saída
        raster_layer = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        canopy_cover_threshold = self.parameterAsDouble(parameters, self.INPUT_CANOPY_COVER_THRESHOLD, context)

        polygon_layer = self.parameterAsVectorLayer(parameters, self.INPUT_POLYGON, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT_RASTER, context)
        csv_path = self.parameterAsFileOutput(parameters, self.OUTPUT_CSV, context)

        chm_ds = gdal.Open(raster_layer.source())
        chm_projection = chm_ds.GetProjection()
        chm_srs = osr.SpatialReference(wkt=chm_projection)

        chm_geotransform = chm_ds.GetGeoTransform()
        pixel_width = abs(chm_geotransform[1])
        pixel_height = abs(chm_geotransform[5])
        
        linear_units_factor = chm_srs.GetLinearUnits()
        pixel_area_native = pixel_height * pixel_width

        pixel_area_m2 = pixel_area_native * (linear_units_factor ** 2)

        chm_band = chm_ds.GetRasterBand(1)
        chm = chm_band.ReadAsArray().astype(np.float32)

        nodata_value = chm_band.GetNoDataValue()
       
        if nodata_value is None:
            nodata_mask = chm is None
        else:
            nodata_mask = chm == nodata_value
        
        if nodata_value is None:
            chm_nodata_count = np.count_nonzero(chm is None)
            canopy_coverage = np.count_nonzero((chm >= canopy_cover_threshold) & (chm is not None)) 
        else:
            chm_nodata_count = np.count_nonzero(chm == nodata_value)
            canopy_coverage = np.count_nonzero((chm >= canopy_cover_threshold) & (chm != nodata_value)) 
        
        total_coverage = np.size(chm) - chm_nodata_count
        canopy_cover_rate = canopy_coverage / total_coverage

        result_raster = -10.47 + 5.56 * chm
        result_raster[nodata_mask] = nodata_value

        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            output_path,
            chm_ds.RasterXSize,
            chm_ds.RasterYSize,
            1,
            gdal.GDT_Float32
        )
        out_ds.SetGeoTransform(chm_geotransform)
        out_ds.SetProjection(chm_projection)
        out_band = out_ds.GetRasterBand(1)
        out_band.SetNoDataValue(nodata_value)
        out_band.WriteArray(result_raster.astype(np.float32))
        out_band.FlushCache()
        out_ds.FlushCache()
        out_ds = None

        if polygon_layer is None:
            csv_results = self.processTotalZonalStats(total_coverage, output_path, pixel_area_m2, context, feedback)
        else:    
            csv_results = self.processPolygonZonalStats(polygon_layer, output_path, pixel_area_m2, context, feedback)
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_results[0].keys())
            writer.writeheader()
            for row in csv_results:
                writer.writerow(row)

        return {
            self.OUTPUT_RASTER: output_path,
            self.OUTPUT_CSV: csv_path
        }

    def processPolygonZonalStats(self, polygon_layer, output_path, pixel_area_m2, context, feedback):
        input_raster_layer = QgsRasterLayer(output_path, "processed_chm")
        if not input_raster_layer.isValid():
            feedback.reportError("Não foi possível criar raster")

        zonal_processing = processing.run("native:zonalstatisticsfb",{
            'INPUT': polygon_layer,
            'INPUT_RASTER': input_raster_layer,
            'COLUMN_PREFIX': '_zst_',
            'STATISTICS': [0, 2], # Count, Mean
            'OUTPUT': 'memory:'
        }, context=context, feedback=feedback)

        result_layer = zonal_processing['OUTPUT']

        csv_results = []
        for feature in result_layer.getFeatures():
            fields = feature.fields()

            current_count = feature['_zst_count']
            current_mean = feature['_zst_mean']

            if current_count is None or current_count == NULL:
                feedback.pushWarning(f"Feature {feature.id()} não cobre nenhum pixel da camada")
                carbon_ton_ha = None
                carbon_kg_m2 = None
                carbon_total_ton = None
                carbon_total_kg = None
            else:
                area_m2 = current_count * pixel_area_m2
                area_ha = area_m2 / 10000
                carbon_ton_ha = current_mean
                carbon_kg_m2 = current_mean / 10
                carbon_total_ton = carbon_ton_ha * area_ha
                carbon_total_kg = carbon_kg_m2 * area_m2

            results = {}
            for name in fields.names():
                if name.startswith('_zst_'):
                    continue
                results[name] = feature[name]
            
            results['Carbon Density (ton/ha)'] = carbon_ton_ha
            results['Carbon Density (kg/m2)'] = carbon_kg_m2
            results['Carbon (ton)'] = carbon_total_ton
            results['Carbon (kg)'] = carbon_total_kg
            csv_results.append(results)
        return csv_results

    def processTotalZonalStats(self, count, output_path, pixel_area_m2, context, feedback):
        out_ds = gdal.Open(output_path)
        out_band = out_ds.GetRasterBand(1)
        _, _, mean, _ = out_band.GetStatistics(0, 1)
        area_m2 = count * pixel_area_m2
        area_ha = area_m2 / 10000
        carbon_ton_ha = mean
        carbon_kg_m2 = carbon_ton_ha / 10
        carbon_total_ton = area_ha * carbon_ton_ha
        carbon_total_kg = area_m2 * carbon_kg_m2
        csv_results = [{
            'ID': -1,
            'Carbon Density (ton/ha)': carbon_ton_ha,
            'Carbon Density (kg/m2)' : carbon_kg_m2,
            'Carbon (ton)': carbon_total_ton,
            'Carbon (kg)': carbon_total_kg
        }]
        return csv_results

    def name(self):
        return 'atlanticnchm'

    def displayName(self):
        return self.tr('Canopy Height Model (CHM)')

    def group(self):
        return self.tr('Carbon Calculator - Atlantic Rainforest')

    def groupId(self):
        return 'atlantic'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return TNC_Carbon_Atlantic_CHM()