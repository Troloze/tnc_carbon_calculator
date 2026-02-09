from qgis.PyQt.QtCore import QCoreApplication # type: ignore
from qgis.core import (QgsProcessingAlgorithm, # type: ignore
                       QgsVectorLayer)
from scipy import stats #type: ignore
import processing #type: ignore
import numpy as np
from .task_managers.csv_exporter import CsvExporter
from .task_managers.geometry_handler import GeometryHandler
from .task_managers.point_cloud_processing import PointCloudProcessor

class TNC_Carbon_Amazonia_Point_Cloud(QgsProcessingAlgorithm):
    IS_DEBUG = True

    geometry_handler = GeometryHandler()
    csv_exporter = CsvExporter()
    point_cloud_processor = PointCloudProcessor()

    def initAlgorithm(self, config=None):
        self.addParameter(
            self.geometry_handler.defineParameter(
                name='POLYGON_INPUT',
                description=self.tr("Polygon Layer (Mask)"), 
                tooltip_info=self.tr(""),
                is_optional=True
            )
        )
        self.addParameter(
            self.geometry_handler.defineIdParameter(
                name='POLYGON_FEATURE_DESCRIPTION_ATTRIBUTE_NAME',
                description=self.tr("Description Attribute Identifier"),
                tooltip_info=self.tr(""),
                is_optional=True
            )
        )
        self.addParameter(
            self.point_cloud_processor.defineParameter(
                name='POINT_CLOUD_INPUT',
                description=self.tr("Point Cloud Layer"),
                tooltip_info=self.tr(""),
                is_optional=False
            )
        )
        self.addParameter(
            self.csv_exporter.defineParameter(
                name='OUTPUT_CSV',
                description=self.tr("CSV Output File Path"),
                tooltip_info=self.tr("")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        self.geometry_handler.initParameter(self, parameters, context, feedback, self.IS_DEBUG)
        self.point_cloud_processor.initParameter(self, parameters, context, feedback, self.IS_DEBUG)
        self.csv_exporter.initParameter(self, parameters, context, feedback, self.IS_DEBUG)

        polygon_data = self.geometry_handler.splitGeometryLayer(self.point_cloud_processor.getCRS())
        partitioned_points = self.point_cloud_processor.partitionPointsByPolygons(polygon_data)
        results = self.point_cloud_processor.applyEquation(self.equation, partitioned_points)

        export_fields = ['ID', 'DESCRIPTION', 'CARBON_KM2', 'CARBON_TONHA', 'CARBON_K', 'CARBON_TON']
        export_field_names = { 
            'ID': 'ID',
            'DESCRIPTION': self.tr('Description'),
            'CARBON_KM2': self.tr('Carbon density (k/m2)'),
            'CARBON_TONHA': self.tr('Carbon density (t/ha)'),
            'CARBON_K': self.tr('Carbon amount (kilograms)'),
            'CARBON_TON': self.tr('Carbon amount (metric tons)')
        }

        # If description attribute name has not been passed, no need to export the empty description column 
        if not self.geometry_handler.hasDescriptionAttribute():
            export_fields.remove('DESCRIPTION')

        # If geometry has not been passed, do not export the total weight of carbon, as point clouds do not have a defined area on their own
        if not self.geometry_handler.hasParameterBeenPassed():
            export_fields.remove('CARBON_K')
            export_fields.remove('CARBON_TON')

        export_data = self.csv_exporter.formatData(
            results, 
            export_fields,
            export_field_names
        )
        self.csv_exporter.exportCsv(export_data)

        return {}

    # Assume you'll obtain a vector with only z values ready for you to do whatever fancy statistics shenanigans you'd ever need to do without the need for conversions or anything like that.
    def equation(self, point_vector):
        if len(point_vector) == 0:
            return {
            "EQ_result": None,
            "EQ_error": None,
            "EQ_hm": None,
            "EQ_h5": None,
            "EQ_h10": None,
            "EQ_h100": None,
            "EQ_hiq": None,
            "EQ_hk": None,
            "EQ_cnt": 0
        }

        hm = float(np.mean(point_vector))
        h5 = float(np.percentile(point_vector, 5)) 
        h10 = float(np.percentile(point_vector, 10))
        h100 = float(np.max(point_vector))
        h25 = float(np.percentile(point_vector, 25))
        h75 = float(np.percentile(point_vector, 75))
        hiq = float(h75 - h25)
        kh = float(stats.kurtosis(point_vector))

        # Equação
        ACD_ALS = 0.2 * (hm ** 2.02) * (abs(kh) ** 0.66) * (h5 ** 0.11) * (h10 ** -0.32) * (hiq ** 0.5) * (h100 ** -0.82)
        sigma = 0.66 * (ACD_ALS ** 0.71) # Desvio padrão

        return {
            "EQ_result": ACD_ALS,
            "EQ_error": sigma,
            "EQ_hm": hm,
            "EQ_h5": h5,
            "EQ_h10": h10,
            "EQ_h100": h100,
            "EQ_hiq": hiq,
            "EQ_hk": kh,
            "EQ_cnt": len(point_vector)
        }

    def name(self):
        return 'amazonpointcloud'

    def displayName(self):
        return self.tr('Point cloud calculator')

    def group(self):
        return self.tr('Carbon Calculator - Amazon')

    def groupId(self):
        return 'amazon'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return TNC_Carbon_Amazonia_Point_Cloud()