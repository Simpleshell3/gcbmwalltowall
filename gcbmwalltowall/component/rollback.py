import json
import pandas as pd
import numpy as np
from collections import defaultdict
from pathlib import Path
from spatial_inventory_rollback.application.app import run as spatial_rollback

class Rollback:

    def __init__(
        self, age_distribution, inventory_year, rollback_year=1990,
        prioritize_disturbances=False, single_draw=False,
        establishment_disturbance_type="Wildfire"
    ):
        self.age_distribution = Path(age_distribution)
        self.inventory_year = inventory_year
        self.rollback_year = rollback_year
        self.prioritize_disturbances = prioritize_disturbances
        self.single_draw = single_draw
        self.establishment_disturbance_type = establishment_disturbance_type
    
    def run(self, classifiers, tiled_layers_path, input_db_path):
        tiled_layers_path = Path(tiled_layers_path).absolute()
        input_db_path = Path(input_db_path).absolute()
        
        output_path = tiled_layers_path.joinpath("..", "rollback")
        output_path.mkdir(parents=True, exist_ok=True)

        inventory_year = self.inventory_year
        if isinstance(inventory_year, str):
            inventory_year = str(next(tiled_layers_path.glob(f"{inventory_year}_moja.tif*")))

        rollback_age_distribution = self.age_distribution
        if rollback_age_distribution.suffix in (".xls", ".xlsx"):
            rollback_age_distribution = output_path.joinpath("age_distribution.json")
            self._convert_age_distribution(classifiers, rollback_age_distribution)

        spatial_rollback(
            input_layers=str(tiled_layers_path),
            input_db=str(input_db_path),
            inventory_year=inventory_year,
            rollback_year=self.rollback_year,
            rollback_age_distribution=str(rollback_age_distribution),
            prioritize_disturbances=self.prioritize_disturbances,
            establishment_disturbance_type=self.establishment_disturbance_type,
            single_draw=self.single_draw,
            output_path=str(output_path),
            stand_replacing_lookup=None)

    def _convert_age_distribution(self, classifiers, output_path):
        age_distributions = []

        root_sheet = pd.read_excel(self.age_distribution, sheet_name="age_distribution")
        distribution_sheets = {
            sheet: list((dist_type for dist_type in dist_types.values() if dist_type))
            for sheet, dist_types in root_sheet.replace([np.nan], [None]).to_dict().items()
        }
    
        for sheet_name, dist_types in distribution_sheets.items():
            distribution = _AgeDistribution(dist_types)
            distribution_sheet = pd.read_excel(self.age_distribution, sheet_name=sheet_name)
        
            for _, row in distribution_sheet.iterrows():
                row_data = dict(zip(distribution_sheet.columns, row))
                classifier_set = {
                    c.name: row_data.get(c.name)
                    for c in classifiers if row_data.get(c.name)
                }

                distribution.add(int(row_data["min_age"]), row_data["proportion"], classifier_set)
        
            age_distributions.extend(distribution.to_json())
    
        json.dump(age_distributions, open(output_path, "w"), indent=4)

class _ClassifierSet(dict):

    def __eq__(self, other):
        return tuple(sorted(self.items())) == tuple(sorted(other.items()))
        
    def __hash__(self):
        return hash(tuple(sorted(self.items())))

class _AgeDistribution:

    def __init__(self, disturbance_types=None):
        self.disturbance_types = disturbance_types
        self.distributions = defaultdict(dict)
        
    def add(self, age, proportion, classifier_set=None):
        classifier_set = _ClassifierSet(classifier_set or {})
        self.distributions[classifier_set][age] = proportion
        
    def to_json(self):
        distributions = []
        for classifier_set, proportions in self.distributions.items():
            distribution = {}
            if self.disturbance_types:
                distribution["disturbance_type"] = list(self.disturbance_types)
            
            if classifier_set:
                for k, v in classifier_set.items():
                    distribution[k] = [v]
                
            distribution["distribution"] = [
                [age, proportion] for age, proportion
                in sorted(proportions.items())
            ]
            
            distributions.append(distribution)
            
        return distributions
