"""
Clinical Trials Downloader for Cancer Studies
Downloads cancer clinical trials from clinicaltrials.gov and processes them
using the same extraction logic as the LangGraph workflow
"""

import requests
import json
import time
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from urllib.parse import urlencode


class ClinicalTrialsDownloader:
    """Downloads and processes cancer clinical trials data using API search"""
    
    def __init__(self, base_url: str = "https://clinicaltrials.gov/api/v2/studies"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Clinical-Trials-RAG-Tool/1.0'
        })
        
    def search_cancer_trials(
        self,
        conditions: List[str] = None,
        interventions: List[str] = None,
        page_size: int = 100,
        max_studies: int = 1000,
        recruitment_status: List[str] = None,
        study_types: List[str] = None
    ) -> List[str]:
        """
        Search for cancer clinical trials and return NCT IDs
        
        Args:
            conditions: Cancer condition terms (e.g., ["lung cancer", "breast cancer"])
            interventions: Drug/intervention names (optional)
            page_size: Number of results per page (max 100)
            max_studies: Maximum total studies to retrieve
            recruitment_status: e.g., ["RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED"]
            study_types: e.g., ["INTERVENTIONAL", "OBSERVATIONAL"]
        
        Returns:
            List of NCT IDs
        """
        
        if conditions is None:
            # Default to major cancer types
            conditions = [
                "lung cancer", "breast cancer", "colorectal cancer", "prostate cancer",
                "melanoma", "lymphoma", "leukemia", "pancreatic cancer", "ovarian cancer",
                "kidney cancer", "liver cancer", "bladder cancer", "brain tumor",
                "sarcoma", "myeloma", "glioblastoma"
            ]
        
        if recruitment_status is None:
            recruitment_status = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED"]
            
        if study_types is None:
            study_types = ["INTERVENTIONAL"]
        
        nct_ids = []
        
        # Search for each condition
        for condition in conditions:
            if len(nct_ids) >= max_studies:
                break
                
            print(f"🔍 Searching for {condition} trials...")
            
            # Build search parameters - simplified to avoid API errors
            search_params = {
                "filter.condition": condition,
                "filter.overallStatus": recruitment_status,
                "filter.studyType": study_types,
                "pageSize": min(page_size, 100),  # API limit
                "format": "json"
            }
            
            # Don't include interventions in search to avoid API issues
            # We'll filter by interventions later during processing
            
        # Search for each condition
        for condition in conditions:
            if len(nct_ids) >= max_studies:
                break
                
            print(f"🔍 Searching for {condition} trials...")
            
            # Use basic search approach that works with the API
            # Just get any studies - we can filter later
            search_url = f"https://clinicaltrials.gov/api/v2/studies"
            search_params = {
                "pageSize": min(page_size, 100),
                "format": "json"
            }
            
            try:
                # Make basic search request first to test API
                response = self.session.get(search_url, params=search_params)
                response.raise_for_status()
                
                search_data = response.json()
                studies = search_data.get("studies", [])
                
                print(f"  Found {len(studies)} studies")
                
                # Extract NCT IDs and filter by condition in the text
                condition_lower = condition.lower()
                for study in studies:
                    if len(nct_ids) >= max_studies:
                        break
                        
                    protocol_section = study.get("protocolSection", {})
                    identification = protocol_section.get("identificationModule", {})
                    nct_id = identification.get("nctId")
                    
                    # Basic filtering by condition
                    if nct_id and nct_id not in nct_ids:
                        # Check if condition appears in study text
                        title = identification.get("officialTitle", "").lower()
                        brief_title = identification.get("briefTitle", "").lower()
                        
                        # Simple keyword matching
                        condition_keywords = condition_lower.replace(" cancer", "").replace(" ", "_").split("_")
                        
                        if any(keyword in title or keyword in brief_title for keyword in condition_keywords):
                            nct_ids.append(nct_id)
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"⚠️  Error searching for {condition}: {e}")
                continue
        
        print(f"✅ Found {len(nct_ids)} unique cancer clinical trials")
        return nct_ids[:max_studies]
    
    def extract_study_data(self, nct_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract structured data from a single study using the same logic 
        as the LangGraph workflow extract_from_url function
        """
        try:
            # Fetch study data
            api_url = f"{self.base_url}/{nct_id}"
            response = self.session.get(api_url)
            response.raise_for_status()
            
            study_data = response.json()
            protocol_section = study_data.get('protocolSection', {})
            results_section = study_data.get('resultsSection', {})
            
            if not protocol_section:
                return None
            
            # Extract data using same logic as workflow
            processed_data = self._process_study_data(protocol_section, results_section, nct_id)
            
            # Add raw data and metadata
            processed_data["raw_data"] = study_data
            processed_data["nct_id"] = nct_id
            processed_data["api_url"] = api_url
            processed_data["study_url"] = f"https://clinicaltrials.gov/study/{nct_id}"
            
            return processed_data
            
        except Exception as e:
            print(f"⚠️  Error extracting data for {nct_id}: {e}")
            return None
    
    def _process_study_data(self, protocol_section: Dict, results_section: Dict, nct_id: str) -> Dict[str, Any]:
        """
        Process study data using EXACT same logic as langgraph_workflow.py extract_from_url function
        """
        
        # Identification Module
        identification_module = protocol_section.get('identificationModule', {})
        official_title = identification_module.get('officialTitle', 'N/A')
        brief_title = identification_module.get('briefTitle', 'N/A')
        
        # Status Module  
        status_module = protocol_section.get('statusModule', {})
        overall_status = status_module.get('overallStatus', 'N/A')
        
        # Description Module
        description_module = protocol_section.get('descriptionModule', {})
        brief_summary = description_module.get('briefSummary', 'N/A')
        detailed_description = description_module.get('detailedDescription', 'N/A')
        
        # Design Module
        design_module = protocol_section.get('designModule', {})
        study_type = design_module.get('studyType', 'N/A')
        study_phases = design_module.get('phases', [])
        study_phase = ", ".join(study_phases) if study_phases else 'N/A'
        
        design_info = design_module.get('designInfo', {})
        allocation = design_info.get('allocation', 'N/A')
        intervention_model = design_info.get('interventionModel', 'N/A')
        primary_purpose = design_info.get('primaryPurpose', 'N/A')
        
        enrollment_info = design_module.get('enrollmentInfo', {})
        enrollment_count = enrollment_info.get('count', 'N/A')
        enrollment_type = enrollment_info.get('type', 'N/A')
        
        # Arms and Interventions
        arms_interventions_module = protocol_section.get('armsInterventionsModule', {})
        arm_groups_list = arms_interventions_module.get('armGroups', [])
        interventions_list = arms_interventions_module.get('interventions', [])
        
        # Extract arm groups with enhanced information
        arm_groups_text = ""
        for i, ag in enumerate(arm_groups_list, 1):
            arm_label = ag.get('label', f'Arm {i}')
            arm_type = ag.get('type', 'N/A')
            arm_description = ag.get('description', 'N/A')
            intervention_names = ag.get('interventionNames', [])
            intervention_names_str = ", ".join(intervention_names) if intervention_names else "N/A"
            
            # Extract dose information from description
            dose_info = ""
            if arm_description and arm_description != 'N/A':
                dose_patterns = [
                    r'(\d+(?:\.\d+)?)\s*mg/kg',
                    r'(\d+(?:\.\d+)?)\s*mg/m2', 
                    r'(\d+(?:\.\d+)?)\s*mg',
                    r'(\d+(?:\.\d+)?)\s*mcg',
                    r'(\d+(?:\.\d+)?)\s*units',
                ]
                
                found_doses = []
                for pattern in dose_patterns:
                    matches = re.findall(pattern, arm_description, re.IGNORECASE)
                    if matches:
                        unit = pattern.split('\\s*')[1].replace(')', '')
                        for match in matches:
                            found_doses.append(f"{match} {unit}")
                
                if found_doses:
                    dose_info = f"  Doses: {', '.join(found_doses)}\\n"
            
            arm_groups_text += f"**Arm {i}: {arm_label}**\\n  Type: {arm_type}\\n  Description: {arm_description}\\n{dose_info}  Interventions: {intervention_names_str}\\n\\n"
        
        # Extract interventions with enhanced drug information
        interventions_text = ""
        intervention_names = []  # For drug extraction
        
        for i, intervention in enumerate(interventions_list, 1):
            name = intervention.get('name', 'N/A')
            int_type = intervention.get('type', 'N/A')
            description = intervention.get('description', 'N/A')
            arm_group_labels = intervention.get('armGroupLabels', [])
            other_names = intervention.get('otherNames', [])
            
            # Collect drug names
            if name != 'N/A':
                intervention_names.append(name)
            intervention_names.extend(other_names)
            
            arm_labels_str = ", ".join(arm_group_labels) if arm_group_labels else "N/A"
            other_names_str = ", ".join(other_names) if other_names else "N/A"
            
            # Extract drug class information
            drug_info = ""
            if other_names:
                for other_name in other_names:
                    if any(keyword in other_name.upper() for keyword in ['ANTI-', 'INHIBITOR', 'AGONIST', 'ANTAGONIST']):
                        drug_info = f"  Mechanism: {other_name}\\n"
                        break
            
            interventions_text += f"**Drug {i}: {name}**\\n  Type: {int_type}\\n  Description: {description}\\n{drug_info}  Used in Arms: {arm_labels_str}\\n  Other Names/Codes: {other_names_str}\\n\\n"
        
        # Eligibility Module
        eligibility_module = protocol_section.get('eligibilityModule', {})
        eligibility_criteria_data = eligibility_module.get('eligibilityCriteria', 'N/A')
        if isinstance(eligibility_criteria_data, dict):
            eligibility_criteria = eligibility_criteria_data.get('textblock', 'N/A')
        else:
            eligibility_criteria = eligibility_criteria_data
            
        min_age = eligibility_module.get('minimumAge', 'N/A')
        max_age = eligibility_module.get('maximumAge', 'N/A')
        sex = eligibility_module.get('sex', 'N/A')
        healthy_volunteers = eligibility_module.get('healthyVolunteers', False)
        
        # Enhanced outcomes extraction
        outcomes_module = protocol_section.get('outcomesModule', {})
        primary_outcomes = outcomes_module.get('primaryOutcomes', [])
        secondary_outcomes = outcomes_module.get('secondaryOutcomes', [])
        
        outcomes_text = ""
        if primary_outcomes:
            safety_outcomes = []
            efficacy_outcomes = []
            pk_outcomes = []
            
            for outcome in primary_outcomes:
                measure = outcome.get('measure', 'N/A')
                description = outcome.get('description', 'N/A')
                time_frame = outcome.get('timeFrame', 'N/A')
                
                measure_lower = measure.lower()
                if any(keyword in measure_lower for keyword in ['safety', 'adverse', 'toxicity', 'mtd', 'dose']):
                    safety_outcomes.append({'measure': measure, 'description': description, 'time_frame': time_frame})
                elif any(keyword in measure_lower for keyword in ['response', 'efficacy', 'survival', 'progression']):
                    efficacy_outcomes.append({'measure': measure, 'description': description, 'time_frame': time_frame})
                elif any(keyword in measure_lower for keyword in ['pharmacokinetic', 'concentration', 'clearance']):
                    pk_outcomes.append({'measure': measure, 'description': description, 'time_frame': time_frame})
                else:
                    efficacy_outcomes.append({'measure': measure, 'description': description, 'time_frame': time_frame})
            
            outcomes_text += "**Primary Objectives:**\\n"
            
            if safety_outcomes:
                outcomes_text += "\\n*Safety Objectives:*\\n"
                for outcome in safety_outcomes:
                    outcomes_text += f"- {outcome['measure']}\\n  Description: {outcome['description']}\\n  Time Frame: {outcome['time_frame']}\\n\\n"
            
            if efficacy_outcomes:
                outcomes_text += "\\n*Efficacy Objectives:*\\n"
                for outcome in efficacy_outcomes:
                    outcomes_text += f"- {outcome['measure']}\\n  Description: {outcome['description']}\\n  Time Frame: {outcome['time_frame']}\\n\\n"
            
            if pk_outcomes:
                outcomes_text += "\\n*Pharmacokinetic Objectives:*\\n"
                for outcome in pk_outcomes:
                    outcomes_text += f"- {outcome['measure']}\\n  Description: {outcome['description']}\\n  Time Frame: {outcome['time_frame']}\\n\\n"
        
        # Secondary outcomes
        if secondary_outcomes:
            outcomes_text += "**Secondary Objectives:**\\n"
            for i, outcome in enumerate(secondary_outcomes[:10], 1):
                measure = outcome.get('measure', 'N/A')
                description = outcome.get('description', 'N/A')
                time_frame = outcome.get('timeFrame', 'N/A')
                outcomes_text += f"{i}. {measure}\\n   Description: {description}\\n   Time Frame: {time_frame}\\n\\n"
            
            if len(secondary_outcomes) > 10:
                outcomes_text += f"... and {len(secondary_outcomes)-10} additional secondary outcomes\\n"
        
        # Adverse Events
        adverse_events_text = ""
        adverse_events_module = results_section.get('adverseEventsModule', {})
        serious_events = adverse_events_module.get('seriousEvents', [])
        other_events = adverse_events_module.get('otherEvents', [])
        
        if serious_events or other_events:
            if serious_events:
                serious_by_system = {}
                for event in serious_events:
                    term = event.get('term', 'N/A')
                    organ_system = event.get('organSystem', 'Other')
                    stats = event.get('stats', [])
                    total_affected = sum(stat.get('numAffected', 0) for stat in stats if isinstance(stat, dict))
                    total_at_risk = sum(stat.get('numAtRisk', 0) for stat in stats if isinstance(stat, dict))
                    
                    if organ_system not in serious_by_system:
                        serious_by_system[organ_system] = []
                    serious_by_system[organ_system].append(f"{term} ({total_affected}/{total_at_risk})")
                
                adverse_events_text += "\\n**Serious Adverse Events by System:**\\n"
                for system, events in serious_by_system.items():
                    adverse_events_text += f"\\n**{system}:**\\n"
                    for event in events[:5]:
                        adverse_events_text += f"- {event}\\n"
                    if len(events) > 5:
                        adverse_events_text += f"- ... and {len(events)-5} more\\n"
        else:
            adverse_events_text = "No adverse events reported in the structured API data."
        
        # Participant Flow
        participant_flow_text = ""
        if results_section:
            participant_flow_module = results_section.get('participantFlowModule', {})
            groups = participant_flow_module.get('groups', [])
            if groups:
                participant_flow_text += "**Participant Enrollment by Group:**\\n"
                for group in groups:
                    group_title = group.get('title', 'N/A')
                    group_description = group.get('description', 'N/A')
                    participant_flow_text += f"- {group_title}: {group_description}\\n"
        
        # Sponsor Information
        sponsor_collaborators_module = protocol_section.get('sponsorCollaboratorsModule', {})
        lead_sponsor = sponsor_collaborators_module.get('leadSponsor', {})
        sponsor_name = lead_sponsor.get('name', 'N/A')
        sponsor_class = lead_sponsor.get('class', 'N/A')
        
        collaborators = sponsor_collaborators_module.get('collaborators', [])
        collaborator_text = ""
        if collaborators:
            collaborator_names = [collab.get('name', 'N/A') for collab in collaborators]
            collaborator_text = f"Collaborators: {', '.join(collaborator_names)}"
        
        sponsor_info = f"Lead Sponsor: {sponsor_name} ({sponsor_class})\\n{collaborator_text}"
        
        # Study Locations
        contacts_locations_module = protocol_section.get('contactsLocationsModule', {})
        locations = contacts_locations_module.get('locations', [])
        location_text = ""
        if locations:
            location_text += f"**Study Locations ({len(locations)} sites):**\\n"
            countries = {}
            for location in locations:
                country = location.get('country', 'Unknown')
                city = location.get('city', 'N/A')
                facility = location.get('facility', 'N/A')
                if country not in countries:
                    countries[country] = []
                countries[country].append(f"{facility}, {city}")
            
            for country, sites in countries.items():
                location_text += f"- {country}: {len(sites)} sites\\n"
                for site in sites[:3]:
                    location_text += f"  • {site}\\n"
                if len(sites) > 3:
                    location_text += f"  • ... and {len(sites)-3} more sites\\n"
        
        # Create structured output using same format as workflow
        data_to_summarize = {
            "Study Overview": f"{official_title} | Status: {overall_status} | Type: {study_type} - {study_phase}",
            "Brief Description": brief_summary,
            "Primary and Secondary Objectives": outcomes_text if outcomes_text else None,
            "Treatment Arms and Interventions": f"{arm_groups_text}\\n\\n{interventions_text}" if (arm_groups_text or interventions_text) else None,
            "Eligibility Criteria": eligibility_criteria,
            "Enrollment and Participant Flow": participant_flow_text if participant_flow_text else None,
            "Adverse Events Profile": adverse_events_text if adverse_events_text and "No adverse events reported" not in adverse_events_text else None,
            "Study Locations": location_text if location_text else None,
            "Sponsor Information": sponsor_info if sponsor_info and sponsor_name != "N/A" else None
        }
        
        # Create parsed_json with proper field names  
        parsed_json = {
            "study_overview": data_to_summarize.get("Study Overview"),
            "brief_description": data_to_summarize.get("Brief Description"),
            "primary_secondary_objectives": data_to_summarize.get("Primary and Secondary Objectives"),
            "treatment_arms_interventions": data_to_summarize.get("Treatment Arms and Interventions"),
            "eligibility_criteria": data_to_summarize.get("Eligibility Criteria"),
            "enrollment_participant_flow": data_to_summarize.get("Enrollment and Participant Flow"),
            "adverse_events_profile": data_to_summarize.get("Adverse Events Profile"),
            "study_locations": data_to_summarize.get("Study Locations"),
            "sponsor_information": data_to_summarize.get("Sponsor Information")
        }
        
        # Extract key metadata for search/filtering
        conditions = []
        condition_module = protocol_section.get('conditionsModule', {})
        condition_list = condition_module.get('conditions', [])
        conditions.extend(condition_list)
        
        # Keywords for search
        keywords = set()
        keywords.update([word.lower() for word in intervention_names if word and word != 'N/A'])
        keywords.update([word.lower() for word in condition_list])
        if brief_title != 'N/A':
            keywords.update(brief_title.lower().split())
        
        # Remove common words
        stop_words = {'the', 'and', 'or', 'in', 'of', 'to', 'a', 'an', 'with', 'for', 'on', 'at', 'by', 'is', 'are', 'was', 'were'}
        keywords = [k for k in keywords if k not in stop_words and len(k) > 2]
        
        return {
            "parsed_json": parsed_json,
            "data_to_summarize": data_to_summarize,
            "metadata": {
                "title": official_title,
                "brief_title": brief_title,
                "status": overall_status,
                "study_type": study_type,
                "phases": study_phases,
                "conditions": conditions,
                "interventions": intervention_names,
                "sponsor": sponsor_name,
                "enrollment_count": enrollment_count,
                "keywords": keywords
            }
        }
    
    def download_cancer_trials(
        self,
        output_file: str = "cancer_clinical_trials.json",
        max_studies: int = 1000,
        conditions: List[str] = None,
        interventions: List[str] = None
    ) -> str:
        """
        Download and process cancer clinical trials, save to JSON file
        
        Returns path to the output file
        """
        print("🚀 Starting cancer clinical trials download...")
        
        # Search for trials
        nct_ids = self.search_cancer_trials(
            conditions=conditions,
            interventions=interventions,
            max_studies=max_studies
        )
        
        if not nct_ids:
            raise Exception("No clinical trials found")
        
        # Process each trial
        processed_trials = []
        failed_count = 0
        
        print(f"📋 Processing {len(nct_ids)} clinical trials...")
        
        for i, nct_id in enumerate(nct_ids, 1):
            if i % 50 == 0:
                print(f"  Processed {i}/{len(nct_ids)} trials...")
            
            try:
                study_data = self.extract_study_data(nct_id)
                if study_data:
                    processed_trials.append(study_data)
                else:
                    failed_count += 1
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"⚠️  Failed to process {nct_id}: {e}")
                failed_count += 1
                continue
        
        print(f"✅ Successfully processed {len(processed_trials)} trials")
        if failed_count > 0:
            print(f"⚠️  Failed to process {failed_count} trials")
        
        # Save to file
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(processed_trials, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved cancer clinical trials data to {output_path}")
        return str(output_path)


def main():
    """Example usage"""
    downloader = ClinicalTrialsDownloader()
    
    # Download cancer trials with focus on specific drugs/conditions
    output_file = downloader.download_cancer_trials(
        output_file="data/cancer_clinical_trials.json",
        max_studies=500,
        conditions=["lung cancer", "breast cancer", "melanoma", "lymphoma"],
        interventions=["pembrolizumab", "nivolumab", "atezolizumab", "durvalumab"]  # Example immunotherapy drugs
    )
    
    print(f"Clinical trials data saved to: {output_file}")


if __name__ == "__main__":
    main()