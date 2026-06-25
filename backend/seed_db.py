import json
import os
from sqlmodel import Session, select
from database import engine
from models import Application, ApplicationSymptom, ApplicationPurpose, ApplicationDependency, ClassificationConfig, UserRole
from services.embedder import TextEmbedder

def seed():
    print("Loading AI Model (E5)... This might take a few seconds.")
    embedder = TextEmbedder()
    
    seed_file = os.path.join(os.path.dirname(__file__), "dummy_seed_data.json")
    if not os.path.exists(seed_file):
        print(f"Error: Could not find {seed_file}")
        return

    with open(seed_file, "r") as f:
        data = json.load(f)
        
    with Session(engine) as session:
        # 1. Seed Applications
        print("Seeding Applications...")
        for app_data in data.get("applications", []):
            existing = session.get(Application, app_data["id"])
            if not existing:
                app = Application(**app_data)
                session.add(app)
        session.commit()
        
        # 2. Seed Application Symptoms (Generates Embeddings!)
        print("Seeding Application Symptoms (Generating Vector Embeddings)...")
        for sym_data in data.get("application_symptoms", []):
            existing = session.exec(
                select(ApplicationSymptom).where(ApplicationSymptom.symptom_text == sym_data["symptom_text"])
            ).first()
            
            if not existing:
                sym = ApplicationSymptom(**sym_data)
                # This generates the 768-dim vector using the E5 model
                sym.embedding = embedder.get_embedding(sym.symptom_text)
                session.add(sym)
        session.commit()
        
        # 3. Seed Application Purposes (Generates Embeddings!)
        print("Seeding Application Purposes (Generating Vector Embeddings)...")
        for purp_data in data.get("application_purposes", []):
            existing = session.exec(
                select(ApplicationPurpose).where(ApplicationPurpose.purpose_text == purp_data["purpose_text"])
            ).first()
            
            if not existing:
                purp = ApplicationPurpose(**purp_data)
                purp.embedding = embedder.get_embedding(purp.purpose_text)
                session.add(purp)
        session.commit()
        
        # 4. Seed Application Dependencies
        print("Seeding Application Dependencies...")
        for dep_data in data.get("application_dependencies", []):
            existing = session.exec(
                select(ApplicationDependency).where(
                    ApplicationDependency.source_app_id == dep_data["source_app_id"],
                    ApplicationDependency.dependent_app_id == dep_data["dependent_app_id"],
                    ApplicationDependency.dependency_nature == dep_data["dependency_nature"]
                )
            ).first()
            
            if not existing:
                dep = ApplicationDependency(**dep_data)
                session.add(dep)
        session.commit()

        # 5. Seed Classification Configs
        print("Seeding Classification Configs...")
        for config_data in data.get("classification_configs", []):
            existing = session.exec(
                select(ClassificationConfig).where(
                    ClassificationConfig.category == config_data["category"],
                    ClassificationConfig.label == config_data["label"]
                )
            ).first()
            
            if not existing:
                conf = ClassificationConfig(**config_data)
                session.add(conf)
        session.commit()
        
        # 6. Seed User Roles (RBAC)
        print("Seeding User Roles (RBAC)...")
        for role_data in data.get("user_roles", []):
            existing = session.get(UserRole, role_data["service_no"])
            if not existing:
                ur = UserRole(**role_data)
                session.add(ur)
        session.commit()
        
        print("Syncing database sequences...")
        from sqlalchemy import text
        try:
            # Fixes PostgreSQL auto-increment counter desync issue
            session.exec(text("SELECT setval('applications_id_seq', (SELECT COALESCE(MAX(id), 1) FROM applications))"))
            session.commit()
        except Exception as e:
            print(f"Note: Sequence sync skipped (if not Postgres). Error: {e}")
            
        print("✅ Database successfully seeded with AI vectors!")

if __name__ == "__main__":
    seed()
