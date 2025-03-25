import os
import logging
import requests
import json
import time
import math
from geopy.geocoders import Nominatim

class PharmacyLocator:
    """
    Class to locate nearby pharmacies using the Overpass API (OpenStreetMap).
    """
    
    def __init__(self):
        """Initialize the PharmacyLocator."""
        self.logger = logging.getLogger(__name__)
        self.overpass_url = "https://overpass-api.de/api/interpreter"
        self.user_agent = "MedicineReminderApp/1.0"
        self.geolocator = Nominatim(user_agent=self.user_agent)
        self.cache = {}  # Cache for geocoding results
        self.cache_timeout = 86400  # 24 hours in seconds
        
    def geocode_address(self, address):
        """
        Convert an address to latitude and longitude.
        
        Args:
            address (str): The address to geocode
            
        Returns:
            tuple: (latitude, longitude) or None if geocoding failed
        """
        try:
            # Check cache first
            if address in self.cache:
                cache_time, result = self.cache[address]
                if time.time() - cache_time < self.cache_timeout:
                    return result
                    
            # If not in cache or cache expired, geocode
            location = self.geolocator.geocode(address)
            
            if location:
                result = (location.latitude, location.longitude)
                self.cache[address] = (time.time(), result)
                return result
            else:
                self.logger.warning(f"Could not geocode address: {address}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error geocoding address {address}: {str(e)}")
            return None
            
    def find_nearby_pharmacies(self, lat, lon, radius=5000):
        """
        Find pharmacies near the given coordinates.
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            radius (int): Search radius in meters (default: 5000)
            
        Returns:
            list: List of pharmacy dictionaries or empty list if error
        """
        try:
            # Construct the Overpass API query
            overpass_query = f"""
            [out:json];
            node[amenity=pharmacy](around:{radius},{lat},{lon});
            out;
            """
            
            # Send request to Overpass API
            response = requests.get(
                self.overpass_url,
                params={'data': overpass_query},
                headers={'User-Agent': self.user_agent}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Process the results
                pharmacies = [
                    {
                        "id": node["id"],
                        "name": node.get("tags", {}).get("name", "Unknown Pharmacy"),
                        "lat": node["lat"],
                        "lon": node["lon"],
                        "address": self._format_address(node.get("tags", {})),
                        "opening_hours": node.get("tags", {}).get("opening_hours", "Unknown"),
                        "phone": node.get("tags", {}).get("phone", node.get("tags", {}).get("contact:phone", "Unknown")),
                        "distance": self._calculate_distance(lat, lon, node["lat"], node["lon"])
                    }
                    for node in data.get("elements", [])
                ]
                
                # Sort by distance
                pharmacies.sort(key=lambda x: x["distance"])
                
                return pharmacies
            else:
                self.logger.error(f"Overpass API error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error finding nearby pharmacies: {str(e)}")
            return []
            
    def find_pharmacies_by_address(self, address, radius=5000):
        """
        Find pharmacies near the given address.
        
        Args:
            address (str): The address to search near
            radius (int): Search radius in meters (default: 5000)
            
        Returns:
            list: List of pharmacy dictionaries or empty list if error
        """
        coordinates = self.geocode_address(address)
        
        if coordinates:
            lat, lon = coordinates
            return self.find_nearby_pharmacies(lat, lon, radius)
        else:
            return []
            
    def _format_address(self, tags):
        """
        Format the address from OSM tags.
        
        Args:
            tags (dict): OpenStreetMap tags
            
        Returns:
            str: Formatted address or "Unknown address"
        """
        # Try to get address from addr:* tags
        address_parts = []
        
        if "addr:housenumber" in tags and "addr:street" in tags:
            address_parts.append(f"{tags['addr:housenumber']} {tags['addr:street']}")
        elif "addr:street" in tags:
            address_parts.append(tags["addr:street"])
            
        if "addr:city" in tags:
            address_parts.append(tags["addr:city"])
            
        if "addr:postcode" in tags:
            address_parts.append(tags["addr:postcode"])
            
        if address_parts:
            return ", ".join(address_parts)
        else:
            # If no structured address, try to use the address tag
            return tags.get("address", "Unknown address")
            
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the distance between two points using the Haversine formula.
        
        Args:
            lat1, lon1: Coordinates of the first point
            lat2, lon2: Coordinates of the second point
            
        Returns:
            float: Distance in kilometers
        """
        # Radius of the Earth in kilometers
        R = 6371.0
        
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Differences
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        # Haversine formula
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        
        return distance
        
    def get_pharmacy_details(self, pharmacy_id):
        """
        Get detailed information about a specific pharmacy.
        
        Args:
            pharmacy_id (int): OpenStreetMap node ID of the pharmacy
            
        Returns:
            dict: Pharmacy details or None if error
        """
        try:
            # Construct the Overpass API query
            overpass_query = f"""
            [out:json];
            node(id:{pharmacy_id});
            out body;
            """
            
            # Send request to Overpass API
            response = requests.get(
                self.overpass_url,
                params={'data': overpass_query},
                headers={'User-Agent': self.user_agent}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if not data.get("elements"):
                    self.logger.warning(f"No pharmacy found with ID {pharmacy_id}")
                    return None
                    
                node = data["elements"][0]
                tags = node.get("tags", {})
                
                return {
                    "id": node["id"],
                    "name": tags.get("name", "Unknown Pharmacy"),
                    "lat": node["lat"],
                    "lon": node["lon"],
                    "address": self._format_address(tags),
                    "opening_hours": tags.get("opening_hours", "Unknown"),
                    "phone": tags.get("phone", tags.get("contact:phone", "Unknown")),
                    "website": tags.get("website", tags.get("contact:website", "Unknown")),
                    "wheelchair": tags.get("wheelchair", "Unknown"),
                    "dispensing": tags.get("dispensing", "Unknown"),
                    "tags": tags
                }
            else:
                self.logger.error(f"Overpass API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting pharmacy details: {str(e)}")
            return None
