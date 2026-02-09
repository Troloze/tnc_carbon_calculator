from .task_class import Task
from qgis.core import (QgsProcessing, # type: ignore                      
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterString,
                       QgsWkbTypes,
                       QgsVectorLayer,
                       QgsUnitTypes,
                       QgsDistanceArea) 
import processing # type: ignore


class GeometryHandler(Task):
    

    def defineParameter(self, name, description, tooltip_info, is_optional = False):
        self.param_name = name
        param = QgsProcessingParameterVectorLayer(
            name=name, 
            description=description, 
            types=[QgsWkbTypes.PolygonGeometry],
            optional=is_optional,  
        )
        param.setHelp(tooltip_info)
        return param

    def defineIdParameter(self, name, description, tooltip_info, is_optional = False):
        self.description_attribute_name = name
        param = QgsProcessingParameterString(
            name=name,
            description=description,
            optional=is_optional
        )
        param.setHelp(tooltip_info)
        return param

    def _readParameter(self):
        if not hasattr(self, "param_name"):
            raise self.ParameterNotDefined()
        self.geometry_layer = self.processing_algorithm.parameterAsVectorLayer(self.processing_parameters, self.param_name, self.processing_context)
        if self.is_debug:
            if self.geometry_layer is None:
                self.processing_feedback.pushInfo(f"(Debug) GeometryHandler._readParameter: geometry_layer features = None")
            else:
                self.processing_feedback.pushInfo(f"(Debug) GeometryHandler._readParameter: geometry_layer features = {self.geometry_layer.featureCount()} polygons")

        self.__has_description_attribute = False
        if not hasattr(self, "description_attribute_name"):
            self.processing_feedback.pushWarning(self.tr("Description Attribute Parameter has not been defined in code. Please contact the developer."))
            return
        self.description_attribute = self.processing_algorithm.parameterAsString(self.processing_parameters, self.description_attribute_name, self.processing_context)
        if self.is_debug:
            self.processing_feedback.pushInfo(f"(Debug) GeometryHandler._readParameter: description_attribute = \"{self.description_attribute}\"")

        if self.description_attribute != "":
            self.__has_description_attribute = True
       
    # With the obtained area, converts to meter squared
    def __getAreaMetersSquared(self, base_area):
        unit_to_unit_factor = QgsUnitTypes.fromUnitToUnitFactor(
            self.__areaCalculator.areaUnits(),
            QgsUnitTypes.AreaSquareMeters
        )
        return base_area * unit_to_unit_factor

    def __getAreaHectare(self, base_area):
        unit_to_unit_factor = QgsUnitTypes.fromUnitToUnitFactor(
            self.__areaCalculator.areaUnits(),
            QgsUnitTypes.AreaHectares
        )
        return base_area * unit_to_unit_factor

    def splitGeometryLayer(self, crs):
        if self.geometry_layer is None:
            self.processing_feedback.pushWarning(self.tr("Geometry layer not provided."))
            return None
        features = self.geometry_layer.getFeatures()
        polygons = []
        self.__areaCalculator = QgsDistanceArea()
        self.__areaCalculator.setSourceCrs(self.geometry_layer.crs(), self.processing_context.transformContext())
        self.__areaCalculator.setEllipsoid(self.processing_context.ellipsoid())
        if self.is_debug:
            self.processing_feedback.pushInfo(f'(Debug) GeometryHandler.splitGeometryLayer: Area Calculator Ellipsoid: {self.processing_context.ellipsoid()}')
        for f in features:
            name = None
            if self.__has_description_attribute:
                if self.description_attribute in f.fields().names():
                    name = f[self.description_attribute]
            base_area = self.__areaCalculator.measureArea(f.geometry())
            if self.is_debug:
                self.processing_feedback.pushInfo(f'(Debug) GeometryHandler.splitGeometryLayer: base_area: {base_area}')
            polygons.append({
                'ID': f.id(),
                'DESCRIPTION': name,
                'POLYGON_LAYER': self.__createTempLayer(f, crs),
                'POLYGON_AREA_M2': self.__getAreaMetersSquared(base_area),
                'POLYGON_AREA_HA': self.__getAreaHectare(base_area)
            })
            if self.is_debug:
                self.processing_feedback.pushInfo(f'(Debug) GeometryHandler.splitGeometryLayer: Polygon {polygons[-1]["ID"]} data')
                self.processing_feedback.pushInfo(f'(Debug) GeometryHandler.splitGeometryLayer:     Polygon Layer: {type(polygons[-1]["POLYGON_LAYER"])} ')
                self.processing_feedback.pushInfo(f'(Debug) GeometryHandler.splitGeometryLayer:     Description Attribute: {polygons[-1]["DESCRIPTION"]}')
                self.processing_feedback.pushInfo(f'(Debug) GeometryHandler.splitGeometryLayer:     Area (Meters Squared): {polygons[-1]["POLYGON_AREA_M2"]}')
                self.processing_feedback.pushInfo(f'(Debug) GeometryHandler.splitGeometryLayer:     Area (Hectares): {polygons[-1]["POLYGON_AREA_HA"]}')
        if self.is_debug:
            self.processing_feedback.pushInfo(f'(Debug) GeometryHandler.splitGeometryLayer: polygon count = {len(polygons)}')
            pass
        
        return polygons

    def __createTempLayer(self, feature, crs):
        temp_layer = QgsVectorLayer(f"Polygon?crs={self.geometry_layer.crs().authid()}", "temp", "memory")
        temp_layer_data = temp_layer.dataProvider()
        temp_layer_data.addAttributes(self.geometry_layer.fields())
        temp_layer.updateFields()
        temp_layer_data.addFeature(feature)
        temp_layer.updateExtents()

        reprojection_result = processing.run("native:reprojectlayer", {
            'INPUT': temp_layer,
            'TARGET_CRS': crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=self.processing_context, feedback=self.processing_feedback)
        return reprojection_result['OUTPUT']

    def hasParameterBeenPassed(self)->bool:
        if not hasattr(self, "processing_algorithm"):
            raise self.ParameterNotInitialized()
        return not self.geometry_layer is None
    
    def hasDescriptionAttribute(self)->bool:
        if not hasattr(self, "processing_algorithm"):
            raise self.ParameterNotInitialized()
        return self.__has_description_attribute