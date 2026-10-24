from enum import Enum

class Mode(str, Enum):
    SIMULATION = "SIMULATION"
    REAL = "REAL"

class Scenario(str, Enum):
    NORMAL = "NORMAL"
    ABNORMAL = "ABNORMAL"
    FAILURE = "FAILURE"
    DEGRADING = "DEGRADING"
    RANDOM = "RANDOM"

class MonitorState:
    def __init__(self):
        self.mode: Mode = Mode.SIMULATION
        self.scenario: Scenario = Scenario.RANDOM
        self.auto_heal: bool = False

    def get_mode(self) -> str:
        return self.mode.value

    def set_mode(self, mode_str: str):
        self.mode = Mode(mode_str.upper())

    def get_scenario(self) -> str:
        return self.scenario.value

    def set_scenario(self, scenario_str: str):
        self.scenario = Scenario(scenario_str.upper())

    def is_auto_heal(self) -> bool:
        return self.auto_heal

    def set_auto_heal(self, auto_heal: bool):
        self.auto_heal = auto_heal

state = MonitorState()
