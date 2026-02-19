__author__ = 'Vitor Di Lorenzzi Nunes da Cunha'
__date__ = '2025-09-25'
__copyright__ = '(C) 2025 by Vitor Di Lorenzzi Nunes da Cunha'

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication # type: ignore
import numpy as np
from qgis.core import (QgsProcessingAlgorithm, # type: ignore
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterPointCloudLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFileDestination,
                       QgsWkbTypes,
                       QgsVectorLayer)

import numpy as np
from scipy import stats #type: ignore
import processing #type: ignore
import csv

class TNC_Carbon_Amazonia_Point_Cloud(QgsProcessingAlgorithm):
    INPUT_POLYGON = 'INPUT_POLYGON'
    INPUT_CLOUD = 'INPUT_POINT_CLOUD'
    INPUT_FILTER = 'INPUT_HEIGH_FILTER'
    OUTPUT = 'OUTPUT_CSV_PATH'

    METRIC_NAMES = {
        "ACD": "Densidade de Carbono",
        "sgm": "Desvio Padrão",
        "hm": "Média",
        "h5": "Percentil 5", 
        "h10": "Percentil 10", 
        "h100": "Percentil 100",
        "hiq": "Intervalo interquartil",
        "kh": "Curtose",
        "cnt": "Contagem de Pontos",
        "id": "ID"
    }

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_POLYGON,
                'Camada de Polígono (máscara)',
                [QgsWkbTypes.PolygonGeometry],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterPointCloudLayer(
                self.INPUT_CLOUD,
                'Camada Raster de Entrada Cloud Point'
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_FILTER, 
                'Filtro de ruído da altura solo (em metros, valor padrão = 0.0m)',
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0,
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                'Arquivo CSV de saída',
                'CSV files (*.csv)'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # Receber camada de núvem de pontos, camada shapefile, e caminho para a saída do CSV
        cloud_layer = self.parameterAsPointCloudLayer(parameters, self.INPUT_CLOUD, context)
        polygon_layer = self.parameterAsVectorLayer(parameters, self.INPUT_POLYGON, context)
        csv_path = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        results = []
        
        if polygon_layer is None:
            # Caso não haja camada de polígonos, processar todos os pontos
            feedback.pushInfo('Shapefile não identificado. Aplicando equação à todos os pontos na camada...')
            valid_points = cloud_layer
            metrics = {self.METRIC_NAMES['id']: -1}
            metrics |= self.apply_equation(valid_points, context, feedback)
            results.append(metrics)
        else:
            # Caso contrário, processar cada polígono individualmente
            total = polygon_layer.featureCount()
            feedback.pushInfo(f'{total} polígono(s) identificado(s).')
            current = 0
            for f in polygon_layer.getFeatures():
                current += 1
                metrics = {}
                if 'id' in f.fields().names():
                    metrics[self.METRIC_NAMES['id']] = f['id']
                else:
                    metrics[self.METRIC_NAMES['id']] = f.id()
                feedback.pushInfo(f'Processando pontos no polígono {f.id()} ({current}/{total})')
                # Cria camada de polígono temporária do formato do polígono atual
                current_polygon = self.create_temp_polygon_layer(polygon_layer, cloud_layer, f, context, feedback)
                feedback.pushInfo(f'SRC da nuvem: {cloud_layer.crs().authid()}')
                feedback.pushInfo(f'SRC do polígono: {current_polygon.crs().authid()}')
                feedback.pushInfo(f'Número de feições no polígono: {current_polygon.featureCount()}')
                clip_result = processing.run("pdal:clip", {
                    'INPUT': cloud_layer,
                    'OVERLAY': current_polygon,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }, context=context, feedback=feedback, is_child_algorithm=False)
                valid_points = clip_result['OUTPUT']
                # Aplica a equação sobre os pontos dentro do polígono temporário
                metrics |= self.apply_equation(valid_points, context, feedback)
                results.append(metrics)

        feedback.pushInfo(f'Processamento finalizado, criando arquivo csv com o resultado em "{csv_path}"')

        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=results[0].keys())
            writer.writeheader()
            for row in results:
                writer.writerow(row)

        return {}

    def create_temp_polygon_layer(self, polygon_layer, cloud_layer, feature, context, feedback):
        temp_layer = QgsVectorLayer("Polygon?crs={}".format(polygon_layer.crs().authid()), "temp", "memory")
        temp_layer_data = temp_layer.dataProvider()
        temp_layer_data.addAttributes(polygon_layer.fields())
        temp_layer.updateFields()
        temp_layer_data.addFeature(feature)
        temp_layer.updateExtents()

        reprojection_result = processing.run("native:reprojectlayer", {
            'INPUT': temp_layer,
            'TARGET_CRS': cloud_layer.crs(),  # EPSG:32722
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }, context=context, feedback=feedback)
        
        return reprojection_result['OUTPUT']
    
    def apply_equation(self, points, context, feedback):
        point_geopackage = processing.run("pdal:exportvector", {
            'INPUT': points,
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }, context=context, feedback=feedback)
            
        z_extract = processing.run("native:extractzvalues", {
            'INPUT': point_geopackage['OUTPUT'],
            'SUMMARIES': [0],
            'COLUMN_PREFIX': 'z_',
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }, context=context, feedback=feedback)

        # Alturas de todos os pontos individualmente
        valid_heights = [f['z_first'] for f in z_extract['OUTPUT'].getFeatures()]
        
        # Caso vazio retornar nulo
        if len(valid_heights) == 0:
            feedback.pushWarning('Nenhum ponto encontrado no polígono')
            return {
            self.METRIC_NAMES["ACD"]: None,
            self.METRIC_NAMES["sgm"]: None,
            self.METRIC_NAMES["hm"]: None,
            self.METRIC_NAMES["h5"]: None,
            self.METRIC_NAMES["h10"]: None,
            self.METRIC_NAMES["h100"]: None,
            self.METRIC_NAMES["hiq"]: None,
            self.METRIC_NAMES["kh"]: None,
            self.METRIC_NAMES["cnt"]: 0
        }

        hm = float(np.mean(valid_heights)) # média
        h5 = float(np.percentile(valid_heights, 5)) # percentil 5
        h10 = float(np.percentile(valid_heights, 10)) # percentil 10
        h100 = float(np.max(valid_heights)) # percentil 100 (ou valor máximo)
        h25 = float(np.percentile(valid_heights, 25))  # quartil 1
        h75 = float(np.percentile(valid_heights, 75))  # quartil 3
        hiq = float(h75 - h25)  # interquartil
        kh = abs(float(stats.kurtosis(valid_heights))) # curtose (!!! Valores não batem com os valores do programa do joão !!!)

        feedback.pushInfo(f"hm: {hm}, h5: {h5}, h10: {h10}, h100: {h100}, hiq: {hiq}, kh: {kh}, cnt: {len(valid_heights)}")

        # Equação
        ACD_ALS = 0.2 * (hm ** 2.02) * (kh ** 0.66) * (h5 ** 0.11) * (h10 ** -0.32) * (hiq ** 0.5) * (h100 ** -0.82)
        sigma = 0.66 * (ACD_ALS ** 0.71) # Desvio padrão

        return {
            self.METRIC_NAMES["ACD"]: ACD_ALS,
            self.METRIC_NAMES["sgm"]: sigma,
            self.METRIC_NAMES["hm"]: hm,
            self.METRIC_NAMES["h5"]: h5,
            self.METRIC_NAMES["h10"]: h10,
            self.METRIC_NAMES["h100"]: h100,
            self.METRIC_NAMES["hiq"]: hiq,
            self.METRIC_NAMES["kh"]: kh,
            self.METRIC_NAMES["cnt"]: len(valid_heights)
        }

    def name(self):
        return 'amazonpointcloud'

    def displayName(self):
        return 'Point Cloud'

    def group(self):
        return 'Calculadora de Carbono - Amazônia'

    def groupId(self):
        return 'amazon'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return TNC_Carbon_Amazonia_Point_Cloud()