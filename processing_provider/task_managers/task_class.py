from abc import ABC, abstractmethod


class Task(ABC):
    
    @abstractmethod
    def defineParameter(self, name, description, tooltip_info, is_optional = False):
        pass

    def initParameter(self, processing_algorithm, processing_parameters, processing_context, processing_feedback, is_debug=False):
        self.processing_algorithm = processing_algorithm
        self.processing_parameters = processing_parameters
        self.processing_context = processing_context
        self.processing_feedback = processing_feedback
        self.tr = processing_algorithm.tr
        self.is_debug = is_debug
        self._readParameter()

    # Called only by initParameter, safe to assume all processing_x attributes have been initialized 
    @abstractmethod
    def _readParameter(self):
        pass
    
    @abstractmethod
    def hasParameterBeenPassed(self)->bool:
        pass

    class ParameterNotDefined(Exception):
        pass

    class ParameterNotInitialized(Exception):
        pass