"""Convert Fusion compositions (DaVinci Resolve, Blackmagic Fusion) to Lottie animations."""
from .comp import CompSyntaxError, Table, parse
from .convert import ConversionError, check, convert

__version__ = "0.1.0"
__all__ = ["CompSyntaxError", "ConversionError", "Table", "check", "convert", "parse"]
