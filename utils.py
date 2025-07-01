from bson import ObjectId
from typing import Any, Dict, List, Union

def convert_objectid_to_str(data: Any) -> Any:
    """
    Converte recursivamente ObjectId para string em estruturas de dados
    """
    if isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, dict):
        return {key: convert_objectid_to_str(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_objectid_to_str(item) for item in data]
    else:
        return data

def serialize_mongo_result(data: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
    """
    Serializa resultados do MongoDB convertendo ObjectId para string
    """
    return convert_objectid_to_str(data)
