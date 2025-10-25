__author__ = 'Vitor Di Lorenzzi Nunes da Cunha'
__date__ = '2025-09-25'
__copyright__ = '(C) 2025 by Vitor Di Lorenzzi Nunes da Cunha'

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication # type: ignore
import numpy as np
from qgis.core import (QgsProcessingAlgorithm, # type: ignore
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterRasterDestination,
                       QgsProcessingParameterFileDestination,
                       QgsWkbTypes,
                       QgsVectorLayer)

from osgeo import gdal, gdal_array, ogr, osr #type: ignore
import numpy as np
from scipy import stats #type: ignore
import processing #type: ignore
import os

class TNC_Biomass_Cerrado_CHM(QgsProcessingAlgorithm):
    INPUT_RASTER = 'INPUT_RASTER'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(self.INPUT_RASTER,'Camada Raster de Entrada CHM')
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Saída'))



    def processAlgorithm(self, parameters, context, feedback):
        raster_layer = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        chm_ds = gdal.Open(raster_layer.source())
        chm = chm_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)

        result = (2.44 + 6.25 * chm)/2 #

        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            output_path,
            chm_ds.RasterXSize,
            chm_ds.RasterYSize,
            1,
            gdal.GDT_UInt16
        )
        out_ds.SetGeoTransform(chm_ds.GetGeoTransform())
        out_ds.SetProjection(chm_ds.GetProjection())
        out_ds.GetRasterBand(1).WriteArray(result.astype(np.uint16))
        out_ds.FlushCache()


        return {self.OUTPUT: output_path}

    def name(self):
        return 'tnc_biomass_cerrado_chm'

    def displayName(self):
        return 'TNC Calculadora de Biomassa Cerrado CHM'

    def group(self):
        return 'Análise de Terreno - Cerrado'

    def groupId(self):
        return 'terrain_analysis_cerrado'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return TNC_Biomass_Cerrado_CHM()