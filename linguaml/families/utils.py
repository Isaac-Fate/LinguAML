from .base import Family
from .svc import SVCFamily
from .logistic import LogisticRegressionFamily

def get_family(name: str) -> Family:
    """Gets the model family by its name.

    Parameters
    ----------
    name : str
        Model family name.

    Returns
    -------
    Family
        An abstract class of the model family.
    """
    
    # Convert to lower case
    name = name.lower().strip()
    
    match name:
        
        case "svc":
            return SVCFamily
        
        case "logistic":
            return LogisticRegressionFamily
        
        case _:
            raise ValueError(f"unkown model family: {name}")
        