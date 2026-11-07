"""
Normalization Service Router

Routes incoming events to the appropriate source-specific normalizer.
"""

from typing import Optional
from app.models.enums import Source
from app.parsers.canonical import infer_source_from_event, resolve_canonical_event_type
from app.parsers.structured import (
    normalize_syslog,
    normalize_network,
    normalize_api,
    normalize_unknown,
)
from app.parsers.cloud import normalize_aws, normalize_crowdstrike
from app.parsers.identity import normalize_ad, normalize_m365


class NormalizationService:
    """Routes events to appropriate source-specific normalizers."""
    
    @staticmethod
    def normalize_event(raw_event: dict, source: Optional[Source] = None) -> dict:
        """
        Normalize a raw event using the appropriate source-specific normalizer.
        
        Args:
            raw_event: The raw event dictionary
            source: Optional source hint. If not provided, will be inferred.
            
        Returns:
            Normalized event dictionary
        """
        # Determine source if not provided
        if source is None:
            source = infer_source_from_event(raw_event)
        
        # Route to appropriate normalizer
        if source == Source.FIREWALL:
            return normalize_syslog(raw_event)
        elif source == Source.NETWORK:
            return normalize_network(raw_event)
        elif source == Source.API:
            return normalize_api(raw_event)
        elif source == Source.CROWDSTRIKE:
            return normalize_crowdstrike(raw_event)
        elif source == Source.AWS:
            return normalize_aws(raw_event)
        elif source == Source.M365:
            return normalize_m365(raw_event)
        elif source == Source.AD:
            return normalize_ad(raw_event)
        else:
            return normalize_unknown(raw_event)