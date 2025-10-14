
__author__ = 'Vitor Di Lorenzzi Nunes da Cunha'
__date__ = '2025-09-25'
__copyright__ = '(C) 2025 by Vitor Di Lorenzzi Nunes da Cunha'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication # type: ignore
from osgeo import gdal # type: ignore
import numpy as np
from qgis.core import (QgsProcessingAlgorithm, # type: ignore
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterRasterDestination)


class TNC_Test_Alg_Multiband(QgsProcessingAlgorithm):

    RED = 'RED'
    GREEN = 'GREEN'
    BLUE = 'BLUE'
    NIR = 'NIR'
    OUTPUT = 'OUTPUT'
    
    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterRasterLayer(self.BLUE, 'Banda Blue'))
        self.addParameter(QgsProcessingParameterRasterLayer(self.GREEN, 'Banda Green'))
        self.addParameter(QgsProcessingParameterRasterLayer(self.RED, 'Banda Red'))
        self.addParameter(QgsProcessingParameterRasterLayer(self.NIR, 'Banda NIR'))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Saída'))

    def processAlgorithm(self, parameters, context, feedback):
        blue_layer = self.parameterAsRasterLayer(parameters, self.BLUE, context)
        green_layer = self.parameterAsRasterLayer(parameters, self.GREEN, context)
        red_layer = self.parameterAsRasterLayer(parameters, self.RED, context)
        nir_layer = self.parameterAsRasterLayer(parameters, self.NIR, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        # Abrir cada raster
        blue_ds = gdal.Open(blue_layer.source())
        green_ds = gdal.Open(green_layer.source())
        red_ds = gdal.Open(red_layer.source())
        nir_ds = gdal.Open(nir_layer.source())

        # Ler banda 1 de cada raster
        blue = blue_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
        green = green_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
        red = red_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
        nir = nir_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)

        # Verificar se todas as imagens têm o mesmo shape
        if not (blue.shape == green.shape == red.shape == nir.shape):
            raise Exception('As imagens de entrada devem ter o mesmo tamanho!')

        # Calcular o máximo por pixel
        result = np.maximum.reduce([blue, green, red, nir])
        result = np.clip(result, 0, 1023)

        # Criar raster de saída
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            output_path,
            blue_ds.RasterXSize,
            blue_ds.RasterYSize,
            1,
            gdal.GDT_UInt16
        )
        out_ds.SetGeoTransform(blue_ds.GetGeoTransform())
        out_ds.SetProjection(blue_ds.GetProjection())
        out_ds.GetRasterBand(1).WriteArray(result.astype(np.uint16))
        out_ds.FlushCache()
        blue_ds = green_ds = red_ds = nir_ds = out_ds = None
        return {self.OUTPUT: output_path}

    def name(self):
        return 'algtest'

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'test'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return TNC_Test_Alg_Multiband()
