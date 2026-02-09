import csv
from .task_class import Task
from qgis.core import QgsProcessingParameterFileDestination # type: ignore


class CsvExporter(Task):

    # Should be called in init function
    def defineParameter(self, name, description, tooltip_info, is_optional = False):
        self.param_name = name
        param = QgsProcessingParameterFileDestination(
            name=name, 
            description=description, 
            fileFilter='CSV files (*.csv)', 
            optional=is_optional, 
            createByDefault=True)
        param.setHelp(tooltip_info)
        return param

    def _readParameter(self):
        if not hasattr(self, "param_name"):
            raise self.ParameterNotDefined()
        self.export_path = self.processing_algorithm.parameterAsFileOutput(self.processing_parameters, self.param_name, self.processing_context)
        if self.is_debug:
            self.processing_feedback.pushInfo(f"(Debug) CsvExporter._readParameter:{self.export_path}")
    
    def formatData(self, data, fields, field_names = None):
        result = []
        for i in data:
            row = {}
            for f in fields:
                if field_names is None:
                    row[f] = i[f]
                    continue
                try:
                    field_name = field_names[f]
                except KeyError:
                    self.processing_feedback.reportError(self.tr("formatDict error: 'field_names' does not match 'fields' structure.\nThis is a bug, please contact the developer"))
                    return self.formatData(data, fields)
                row[field_name] = i[f]
            result.append(row)
        return result
        
    def exportCsv(self, data):      
        if self.export_path == "":
            self.processing_feedback.pushWarning(self.tr("Path not provided. CSV file was not exported."))
            return
        with open(self.export_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        self.processing_feedback.pushInfo(self.tr("Successfully exported csv at:"))
        self.processing_feedback.pushInfo(f"{self.export_path}")
        
    def hasParameterBeenPassed(self)->bool:
        if not hasattr(self, "processing_algorithm"):
            raise self.ParameterNotInitialized()
        return not self.export_path == ""
