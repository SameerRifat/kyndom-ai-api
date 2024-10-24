import csv
from datetime import datetime
import logging
from typing import Tuple, List, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class CSVService:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.headers = None
        self.formatted_dates = None
        self.load_and_parse_csv()

    def load_and_parse_csv(self) -> bool:
        try:
            with open(self.csv_path, 'r') as file:
                csv_reader = csv.reader(file)
                self.headers = next(csv_reader)
                
                if not self.headers:
                    raise ValueError("CSV file is empty or contains only whitespace")
                
                date_columns = self.headers[8:]
                self.formatted_dates = []
                for date in date_columns:
                    try:
                        parsed_date = datetime.strptime(date, '%d/%m/%Y')
                    except ValueError:
                        try:
                            parsed_date = datetime.strptime(date, '%Y-%m-%d')
                        except ValueError as e:
                            logger.error(f"Error parsing date {date}: {e}")
                            self.formatted_dates.append(date)
                            continue
                    
                    formatted_date = parsed_date.strftime('%Y-%m-%d')
                    self.formatted_dates.append(formatted_date)
                
                return True
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}")
            return False

    def get_zhvi_data(self, region_name: str, state_name: str) -> Tuple[List[str], dict]:
        if not self.headers or not self.formatted_dates:
            raise HTTPException(status_code=500, detail="ZHVI data not properly initialized")
        
        try:
            with open(self.csv_path, 'r') as file:
                csv_reader = csv.reader(file)
                next(csv_reader)  # Skip headers
                
                for row in csv_reader:
                    if len(row) < 8:
                        continue
                    
                    if (row[2].lower() == region_name.lower() and 
                        row[4].lower() == state_name.lower()):
                        record = {
                            "RegionID": int(row[0]) if row[0].isdigit() else 0,
                            "SizeRank": int(row[1]) if row[1].isdigit() else 0,
                            "RegionName": row[2],
                            "RegionType": row[3],
                            "StateName": row[4],
                            "State": row[5],
                            "Metro": row[6],
                            "CountyName": row[7]
                        }
                        
                        for i, date in enumerate(self.formatted_dates):
                            try:
                                value = float(row[i + 8]) if row[i + 8] else None
                                record[date] = value
                            except (IndexError, ValueError):
                                record[date] = None
                        
                        return self.formatted_dates, record
            
            raise HTTPException(
                status_code=404, 
                detail=f"No data found for {region_name}, {state_name}"
            )
        
        except Exception as e:
            logger.exception("An error occurred in get_zhvi_data")
            raise HTTPException(status_code=500, detail=str(e))