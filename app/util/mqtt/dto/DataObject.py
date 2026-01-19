from dataclasses import dataclass
import json

@dataclass
class PathPayload:
    current_node: int
    final_node: int
    start_node: int
    table_id: int
    robot_id: int
    map_name: str