### 
### Arquivo de teste, ignore isso aqui
###
__author__ = 'Vitor Di Lorenzzi Nunes da Cunha'
__date__ = '2025-09-25'
__copyright__ = '(C) 2025 by Vitor Di Lorenzzi Nunes da Cunha'

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication # type: ignore
import numpy as np
from qgis.core import (QgsProcessingAlgorithm, # type: ignore
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingOutputNumber,
                       QgsProcessingParameterNumber,
                       QgsWkbTypes)

from osgeo import gdal, gdal_array, ogr, osr #type: ignore
import numpy as np
from scipy import stats #type: ignore
import processing #type: ignore
import os

class TNC_Biomass_V1(QgsProcessingAlgorithm):
    INPUT_RASTER = 'INPUT_RASTER'
    INPUT_POLYGON = 'INPUT_POLYGON'
    OUTPUT = 'OUTPUT'
    STANDARD_DEVIATION = 'STANDARD DEVIATION'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(self.INPUT_RASTER,'Camada Raster de entrada')
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(self.INPUT_POLYGON,'Camada de Polígono (máscara)',[QgsWkbTypes.PolygonGeometry])
        )
        self.addOutput(
            QgsProcessingOutputNumber(self.OUTPUT,'Média das Alturas')
        )
        self.addOutput(
            QgsProcessingOutputNumber(self.STANDARD_DEVIATION,'Margem de Erro')
        )


    def processAlgorithm(self, parameters, context, feedback):
        raster_layer = self.parameterAsRasterLayer(parameters, self.INPUT_RASTER, context)
        polygon_layer = self.parameterAsVectorLayer(parameters, self.INPUT_POLYGON, context)

        clip_result = processing.run("gdal:cliprasterbymasklayer", {
            'INPUT': raster_layer.source(),  # Caminho do arquivo
            'MASK': polygon_layer.source(),  # Caminho do arquivo
            'NODATA': -9999,
            'CROP_TO_CUTLINE': True,
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }, context=context, feedback=feedback)

        output_path = clip_result['OUTPUT']
        if not os.path.exists(output_path):
            raise Exception(f'Arquivo de saída não foi criado: {output_path}')
        
        # Abrir o resultado clippado
        clipped_raster = gdal.Open(clip_result['OUTPUT'])
        height_array = clipped_raster.GetRasterBand(1).ReadAsArray()
        
        # Remover valores NoData e calcular estatísticas
        nodata = clipped_raster.GetRasterBand(1).GetNoDataValue()
        if nodata is not None:
            valid_heights = height_array[height_array != nodata]
        else:
            valid_heights = height_array.flatten()
        
        hm = float(np.mean(valid_heights)) # média
        h5 = float(np.percentile(valid_heights, 5)) # percentil 5
        h10 = float(np.percentile(valid_heights, 10)) # percentil 10
        h100 = float(np.max(valid_heights)) # percentil 100 (ou valor máximo)
        h25 = float(np.percentile(valid_heights, 25))  # quartil 1
        h75 = float(np.percentile(valid_heights, 75))  # quartil 3
        hiq = float(h75 - h25)  # interquartil
        kh = float(stats.kurtosis(valid_heights)) # curtose

        ACD_ALS = 0.2 * (hm ** 2.02) * (kh ** 0.66) * (h5 ** 0.11) * (h10 ** -0.32) * (hiq ** 0.5) * (h100 ** -0.82)

        sigma = 0.66 * (ACD_ALS ** 0.71) # Desvio padrão

        feedback.pushInfo(f'ACD_ALS calculado: {ACD_ALS:.2f}')
        feedback.pushInfo(f'Desvio padrão: ±{sigma:.2f}')
        feedback.pushInfo(f'Pixels processados: {len(valid_heights)}')

        return {self.OUTPUT: ACD_ALS,
                self.STANDARD_DEVIATION: sigma}

      
    def name(self):
        return 'tnc_biomass_v1'

    def displayName(self):
        return 'TNC Calculadora de Biomassa v1'

    def group(self):
        return 'Análise de Terreno'

    def groupId(self):
        return 'terrain_analysis'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return TNC_Biomass_V1()