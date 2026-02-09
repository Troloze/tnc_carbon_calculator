from .task_class import Task
from qgis.core import (QgsProcessing, # type: ignore
                       QgsPointCloudLayer,
                       QgsProcessingParameterPointCloudLayer) 


import processing # type: ignore
from typing import Callable, List, Dict

class PointCloudProcessor(Task):
    
    def defineParameter(self, name, description, tooltip_info, is_optional = False):
        self.param_name = name
        param = QgsProcessingParameterPointCloudLayer(
            name=name, 
            description=description, 
            optional=is_optional,  
        )
        param.setHelp(tooltip_info)
        return param

    def _readParameter(self):
        if not hasattr(self, "param_name"):
            raise self.ParameterNotDefined()
        self.point_cloud_layer = self.processing_algorithm.parameterAsPointCloudLayer(self.processing_parameters, self.param_name, self.processing_context)
        
    def getCRS(self):
        if self.hasParameterBeenPassed():
            return self.point_cloud_layer.crs()
        else: 
            return None
    
    def partitionPointsByPolygons(self, polygon_data:List|None):
        if not hasattr(self, "processing_algorithm"):
            raise self.ParameterNotInitialized()
        if polygon_data is None:
            return [{'ID': 0, 'DESCRIPTION_ATTRIBUTE': '', 'POLYGON_LAYER': None, 'POLYGON_AREA_M2': 0, 'POLYGON_AREA_HA': 0, 'POINTS': self.point_cloud_layer}]
        polygon_total = len(polygon_data)
        polygon_count = 0
        for p in polygon_data:
            polygon_count += 1
            polygon_layer = p['POLYGON_LAYER']
            if self.is_debug:
                self.processing_feedback.pushInfo(f'(Debug) Tipo de POLYGON_LAYER: {type(polygon_layer)}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.partitionPointsByPolygons: Processing {polygon_count}/{polygon_total}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.partitionPointsByPolygons:     Point Cloud CRS = {self.point_cloud_layer.crs().authid()}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.partitionPointsByPolygons:     Polygon CRS = {polygon_layer.crs().authid()}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.partitionPointsByPolygons:     Polygon Features = {polygon_layer.featureCount()} (expected: 1)')
            partitioned_points = processing.run("pdal:clip", {
                    'INPUT': self.point_cloud_layer,
                    'OVERLAY': polygon_layer,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=self.processing_context, feedback=self.processing_feedback)
            p['POINTS'] = partitioned_points['OUTPUT']
        return polygon_data
    
    def applyEquation(self, equation:Callable[[List], Dict], partitioned_points:List):
        if not hasattr(self, "processing_algorithm"):
            raise self.ParameterNotInitialized()
        partition_total = len(partitioned_points)
        partition_count = 0
        for pp in partitioned_points:
            partition_count += 1
            points = pp['POINTS']


            # Converting to a vector layer and extracting z values from its features is a slow process
            # However, as of the moment i write this, I cannot obtain the index from the data provider of
            # A point cloud layer, which would allow me to do all of this without having to use these 
            # Expensive processes.
            # Consider changing this in the future.
            points_gpkg = processing.run("pdal:exportvector", {
                    'INPUT': points,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=self.processing_context, feedback=self.processing_feedback)
            
            z_values_raw = processing.run("native:extractzvalues", {
                    'INPUT': points_gpkg['OUTPUT'],
                    'SUMMARIES': [0],
                    'COLUMN_PREFIX': 'z_',
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=self.processing_context, feedback=self.processing_feedback)
            
            z_values = [f['z_first'] for f in z_values_raw['OUTPUT'].getFeatures()]
            
            
            result = equation(z_values)
            if self.is_debug:
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.applyEquation: Result = {result["EQ_result"]}; Error = {result["EQ_error"]}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.applyEquation:     Average: {result["EQ_hm"]}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.applyEquation:     5 Percent: {result["EQ_h5"]}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.applyEquation:     10 Percent: {result["EQ_h10"]}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.applyEquation:     Interquartile: {result["EQ_hiq"]}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.applyEquation:     Curtosis: {result["EQ_hk"]}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.applyEquation:     100 percent: {result["EQ_h100"]}')
                self.processing_feedback.pushInfo(f'(Debug) pointCloudProcessor.applyEquation:     Point Count: {result["EQ_cnt"]}')
            carbon_k_m2 = result['EQ_result'] 
            carbon_ton_ha = carbon_k_m2 * 10
            carbon_k = carbon_k_m2 * pp['POLYGON_AREA_M2']
            carbon_ton = carbon_ton_ha * pp['POLYGON_AREA_HA']
            
            pp['CARBON_KM2'] = carbon_k_m2
            pp['CARBON_TONHA'] = carbon_ton_ha
            pp['CARBON_K'] = carbon_k
            pp['CARBON_TON'] = carbon_ton
        return partitioned_points


    def partitionPointsByGrid(self, grid):
        pass

    def hasParameterBeenPassed(self)->bool:
        if not hasattr(self, "processing_algorithm"):
            raise self.ParameterNotInitialized()
        return not self.point_cloud_layer is None