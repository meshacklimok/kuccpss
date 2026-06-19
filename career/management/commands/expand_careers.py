"""
Management command: expand_careers
Adds new CareerProfile records and keyword-links all courses.Course objects
to the correct career profiles. Safe to run multiple times (idempotent).

Usage:
    python manage.py expand_careers            # add profiles + link courses
    python manage.py expand_careers --link-only # skip profile creation, just re-link
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from career.models import CareerProfile
from courses.models import Course


# ── Career profiles to create / update ──────────────────────────────────────
# Each entry: title, icon, demand_level, average_salary, career_tags,
#             description, keywords (for course linking)
NEW_CAREERS = [
    # ── HEALTH ──────────────────────────────────────────────────────────────
    {
        "title": "Veterinarian",
        "icon": "fas fa-paw",
        "demand_level": "high",
        "average_salary": "KSh 60,000 – 200,000/month",
        "career_tags": "health,science,agriculture",
        "description": (
            "Veterinarians diagnose and treat diseases in animals, safeguard food safety, "
            "and support Kenya's livestock economy. They work with pets, farm animals, and "
            "wildlife in settings ranging from rural farms to Nairobi National Park."
        ),
        "duties": (
            "• Examine, diagnose and treat sick or injured animals\n"
            "• Administer vaccines and preventive medicine\n"
            "• Perform surgical procedures on animals\n"
            "• Advise farmers on animal health and husbandry\n"
            "• Inspect meat and dairy products for food safety\n"
            "• Conduct disease surveillance for zoonotic illnesses"
        ),
        "skills_required": (
            "• Strong science foundation (Biology, Chemistry)\n"
            "• Precision and attention to detail\n"
            "• Physical stamina for farm and field work\n"
            "• Communication skills for farmer advisory\n"
            "• Empathy for animals"
        ),
        "educational_pathway": (
            "• KCSE: B+ or above, strong in Biology and Chemistry\n"
            "• Bachelor of Veterinary Medicine (BVM) — 5 years at UoN, Egerton, CAVS\n"
            "• Registration with Kenya Veterinary Board\n"
            "• Optional: MSc in Veterinary Epidemiology or Animal Science"
        ),
        "job_opportunities": (
            "Private practice, Ministry of Agriculture, Kenya Wildlife Service (KWS), "
            "food processing companies, NGOs, pharmaceutical companies, research institutions"
        ),
        "future_outlook": (
            "Rising demand due to growth in dairy, poultry, and aquaculture sectors. "
            "Wildlife tourism and disease surveillance also drive need for vets."
        ),
        "keywords": ["veterinary", "animal health", "animal science", "zoology", "wildlife management"],
    },
    {
        "title": "Dental Surgeon",
        "icon": "fas fa-tooth",
        "demand_level": "high",
        "average_salary": "KSh 80,000 – 300,000/month",
        "career_tags": "health,science",
        "description": (
            "Dental surgeons diagnose and treat conditions of the teeth, mouth, and jaw. "
            "Kenya has a significant shortage of dentists, creating strong career opportunities "
            "in both public hospitals and private clinics."
        ),
        "duties": (
            "• Examine patients and diagnose oral conditions\n"
            "• Fill, extract, and replace teeth\n"
            "• Treat gum disease (periodontics)\n"
            "• Fit crowns, bridges, and dentures\n"
            "• Perform oral surgeries\n"
            "• Educate patients on oral hygiene"
        ),
        "skills_required": (
            "• Manual dexterity and precision\n"
            "• Strong science background\n"
            "• Attention to detail\n"
            "• Good interpersonal and calming skills\n"
            "• Problem-solving in clinical settings"
        ),
        "educational_pathway": (
            "• KCSE: B+ or above in Biology, Chemistry\n"
            "• Bachelor of Dental Surgery (BDS) — 5 years at UoN or Moi University\n"
            "• Internship (1 year) at a public hospital\n"
            "• Registration with Kenya Medical Practitioners and Dentists Council"
        ),
        "job_opportunities": (
            "Government hospitals, private dental clinics, NGO health programs, "
            "military and police health services, corporate health facilities"
        ),
        "future_outlook": (
            "Kenya has fewer than 1,500 registered dentists for 55 million people — one of "
            "the biggest gaps in healthcare. Demand is guaranteed to grow for decades."
        ),
        "keywords": ["dental", "dentistry", "oral health", "dental surgery", "dental technology"],
    },
    {
        "title": "Physiotherapist",
        "icon": "fas fa-walking",
        "demand_level": "high",
        "average_salary": "KSh 50,000 – 150,000/month",
        "career_tags": "health,science",
        "description": (
            "Physiotherapists help patients recover from injuries, surgeries, and chronic "
            "conditions through physical rehabilitation, exercise, and manual therapy."
        ),
        "duties": (
            "• Assess patients' physical condition and mobility\n"
            "• Design and implement rehabilitation programs\n"
            "• Use electrotherapy, ultrasound, and manual techniques\n"
            "• Guide patients through therapeutic exercises\n"
            "• Manage musculoskeletal, neurological, and respiratory conditions\n"
            "• Work with athletes on injury prevention"
        ),
        "skills_required": (
            "• Anatomy and physiology knowledge\n"
            "• Physical fitness and stamina\n"
            "• Empathy and patience\n"
            "• Analytical and problem-solving skills\n"
            "• Communication and motivational ability"
        ),
        "educational_pathway": (
            "• KCSE: B or above in Biology, Chemistry\n"
            "• Bachelor of Science in Physiotherapy — 4 years at UoN, Moi, KMTC\n"
            "• Internship (1 year)\n"
            "• Registration with Kenya Physiotherapists and Occupational Therapists Board"
        ),
        "job_opportunities": (
            "Hospitals, rehabilitation centres, sports clubs, private clinics, "
            "armed forces, corporate wellness programs, NGO health missions"
        ),
        "future_outlook": (
            "Growing sports industry and ageing population drive demand. "
            "Telehealth physiotherapy is expanding rapidly post-COVID."
        ),
        "keywords": ["physiotherapy", "physical therapy", "rehabilitation", "occupational therapy", "orthopedic"],
    },
    {
        "title": "Nutritionist & Dietitian",
        "icon": "fas fa-apple-alt",
        "demand_level": "high",
        "average_salary": "KSh 45,000 – 130,000/month",
        "career_tags": "health,science,food",
        "description": (
            "Nutritionists and dietitians advise individuals and communities on healthy eating, "
            "manage therapeutic diets for patients, and address Kenya's nutrition challenges "
            "including malnutrition, diabetes, and obesity."
        ),
        "duties": (
            "• Assess clients' nutritional status and dietary needs\n"
            "• Design personalised meal plans and therapeutic diets\n"
            "• Counsel patients with diabetes, hypertension, kidney disease\n"
            "• Conduct community nutrition programs and school feeding initiatives\n"
            "• Conduct food safety and quality checks\n"
            "• Research on food systems and nutrition policy"
        ),
        "skills_required": (
            "• Food science and biochemistry knowledge\n"
            "• Counselling and communication skills\n"
            "• Attention to detail in dietary analysis\n"
            "• Cultural sensitivity (Kenyan food traditions)\n"
            "• Research and data analysis"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above in Biology, Chemistry\n"
            "• BSc Nutrition and Dietetics or Food Science — 4 years\n"
            "• Internship in a hospital dietetics department\n"
            "• Registration with Kenya Nutritionists and Dietitians Institute (KNDI)"
        ),
        "job_opportunities": (
            "Public hospitals, private clinics, schools, food companies, NGOs, "
            "World Food Programme, UNICEF, research institutions, hotels"
        ),
        "future_outlook": (
            "Rising non-communicable diseases (NCDs) and malnutrition create "
            "strong demand. Corporate wellness programs are a growing market."
        ),
        "keywords": ["nutrition", "dietetics", "food science", "food technology", "food and nutrition", "nutraceutical"],
    },
    {
        "title": "Medical Laboratory Technologist",
        "icon": "fas fa-microscope",
        "demand_level": "very_high",
        "average_salary": "KSh 40,000 – 120,000/month",
        "career_tags": "health,science",
        "description": (
            "Medical laboratory scientists analyze blood, tissue, urine, and other samples "
            "to help doctors diagnose and monitor diseases. They are the backbone of modern "
            "clinical diagnosis in Kenya."
        ),
        "duties": (
            "• Collect and process biological samples\n"
            "• Perform blood counts, cultures, urinalysis, and biochemistry tests\n"
            "• Operate and maintain laboratory equipment\n"
            "• Analyse results and report findings to clinicians\n"
            "• Conduct HIV, TB, malaria, and COVID-19 diagnostic tests\n"
            "• Maintain quality assurance and biosafety standards"
        ),
        "skills_required": (
            "• Biology and Chemistry competence\n"
            "• Precision and technical accuracy\n"
            "• Ability to work under pressure\n"
            "• Knowledge of laboratory safety protocols\n"
            "• Good observation and analytical skills"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above in Biology, Chemistry\n"
            "• Diploma in Medical Laboratory Sciences (KMTC — 3 years) OR\n"
            "• BSc Medical Laboratory Sciences — 4 years at UoN, JKUAT, Moi\n"
            "• Registration with Kenya Medical Laboratory Technicians and Technologists Board"
        ),
        "job_opportunities": (
            "Government hospitals, private hospitals, reference laboratories (KEMRI), "
            "blood transfusion services, NGO clinics, research institutions"
        ),
        "future_outlook": (
            "Post-pandemic investment in diagnostics infrastructure is driving demand. "
            "Molecular biology and genomics are opening new specialisations."
        ),
        "keywords": ["medical laboratory", "laboratory sciences", "laboratory technology", "haematology",
                     "clinical biochemistry", "microbiology", "parasitology", "pathology"],
    },
    {
        "title": "Radiographer",
        "icon": "fas fa-x-ray",
        "demand_level": "high",
        "average_salary": "KSh 50,000 – 130,000/month",
        "career_tags": "health,science,technology",
        "description": (
            "Radiographers produce diagnostic images (X-rays, CT scans, MRIs, ultrasounds) "
            "that doctors use to diagnose and plan treatment for illness and injury."
        ),
        "duties": (
            "• Operate X-ray, CT, MRI, and ultrasound machines\n"
            "• Position patients correctly for imaging procedures\n"
            "• Maintain radiation safety standards\n"
            "• Process and quality-check images\n"
            "• Assist radiologists in interventional procedures\n"
            "• Maintain equipment and quality assurance records"
        ),
        "skills_required": (
            "• Physics and Biology background\n"
            "• Technical aptitude for imaging equipment\n"
            "• Attention to detail and precision\n"
            "• Good communication (working with anxious patients)\n"
            "• Radiation safety knowledge"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above in Biology, Physics, Chemistry\n"
            "• Diploma in Medical Imaging Sciences (KMTC) OR\n"
            "• BSc Medical Imaging Sciences — 4 years\n"
            "• Registration with Kenya Medical Laboratory Technicians and Technologists Board"
        ),
        "job_opportunities": (
            "Government and private hospitals, diagnostic imaging centres, cancer centres, "
            "mobile imaging units, military health services"
        ),
        "future_outlook": (
            "Expansion of county referral hospitals and cancer screening programs "
            "will significantly increase radiographer demand."
        ),
        "keywords": ["radiology", "radiography", "medical imaging", "ultrasound", "sonography",
                     "radiological", "diagnostic imaging"],
    },
    {
        "title": "Optometrist",
        "icon": "fas fa-eye",
        "demand_level": "high",
        "average_salary": "KSh 50,000 – 150,000/month",
        "career_tags": "health,science",
        "description": (
            "Optometrists examine eyes, diagnose vision problems and eye diseases, "
            "prescribe corrective lenses, and provide primary eye care across Kenya."
        ),
        "duties": (
            "• Perform comprehensive eye examinations\n"
            "• Diagnose conditions like myopia, glaucoma, cataracts, diabetic retinopathy\n"
            "• Prescribe spectacles, contact lenses, and low-vision aids\n"
            "• Provide pre- and post-operative care for eye surgeries\n"
            "• Run community eye health screening programs\n"
            "• Dispense and fit corrective eyewear"
        ),
        "skills_required": (
            "• Biology, Physics, and Chemistry knowledge\n"
            "• Fine motor skills and precision\n"
            "• Good communication and empathy\n"
            "• Analytical thinking and diagnostic ability\n"
            "• Business skills for private practice management"
        ),
        "educational_pathway": (
            "• KCSE: B or above in Biology, Physics, Chemistry\n"
            "• Bachelor of Science in Optometry — 4–5 years at UoN or Masinde Muliro\n"
            "• Internship (1 year)\n"
            "• Registration with Kenya Vision Institute / Optical Board"
        ),
        "job_opportunities": (
            "Private optical shops, hospitals, NGO eye health programs (e.g., Sightsavers, AMREF), "
            "school vision screening, research institutions"
        ),
        "future_outlook": (
            "Kenya has a major backlog of uncorrected vision impairment. "
            "Growing middle class and smartphone use are driving demand for eye care."
        ),
        "keywords": ["optometry", "optician", "optics", "vision science", "eye"],
    },
    {
        "title": "Public Health Officer",
        "icon": "fas fa-shield-virus",
        "demand_level": "very_high",
        "average_salary": "KSh 45,000 – 130,000/month",
        "career_tags": "health,governance,science",
        "description": (
            "Public health officers protect communities from disease outbreaks, promote healthy "
            "lifestyles, and ensure environmental sanitation. They work at county and national "
            "government levels, NGOs, and international health organisations."
        ),
        "duties": (
            "• Conduct disease surveillance and outbreak investigations\n"
            "• Inspect food premises, water sources, and sanitation facilities\n"
            "• Implement immunisation programs\n"
            "• Lead health education and promotion campaigns\n"
            "• Collect and analyse public health data\n"
            "• Coordinate emergency health responses"
        ),
        "skills_required": (
            "• Epidemiology and statistics\n"
            "• Environmental health knowledge\n"
            "• Leadership and community mobilisation\n"
            "• Report writing and data analysis\n"
            "• Knowledge of Kenya's health policies and laws"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above in Biology, Chemistry\n"
            "• Diploma in Public Health (KMTC — 3 years) OR\n"
            "• BSc Public Health or Environmental Health — 4 years\n"
            "• Optional: MPH (Master of Public Health)"
        ),
        "job_opportunities": (
            "County health departments, Ministry of Health, WHO, UNICEF, KEMRI, CDC, "
            "international NGOs, water and sanitation organisations"
        ),
        "future_outlook": (
            "COVID-19 permanently elevated global investment in public health systems. "
            "Kenya's UHC rollout will absorb thousands of public health officers."
        ),
        "keywords": ["public health", "environmental health", "epidemiology", "community health",
                     "health promotion", "health management", "population health", "health policy"],
    },
    # ── ENGINEERING ─────────────────────────────────────────────────────────
    {
        "title": "Chemical Engineer",
        "icon": "fas fa-flask",
        "demand_level": "high",
        "average_salary": "KSh 80,000 – 250,000/month",
        "career_tags": "engineering,science",
        "description": (
            "Chemical engineers design processes and equipment to transform raw materials "
            "into useful products — from medicines and fertilisers to petroleum and plastics. "
            "Kenya's growing manufacturing sector is driving demand."
        ),
        "duties": (
            "• Design chemical manufacturing processes and equipment\n"
            "• Oversee production in refineries, breweries, and factories\n"
            "• Ensure compliance with health, safety, and environmental regulations\n"
            "• Troubleshoot process issues and optimise efficiency\n"
            "• Conduct quality control and product testing\n"
            "• Develop new materials and processes through research"
        ),
        "skills_required": (
            "• Strong Chemistry and Mathematics\n"
            "• Process design and thermodynamics\n"
            "• Computer simulation (ASPEN, MATLAB)\n"
            "• Problem-solving and analytical thinking\n"
            "• Health and safety awareness"
        ),
        "educational_pathway": (
            "• KCSE: B+ in Mathematics, Chemistry, Physics\n"
            "• BSc Chemical Engineering — 4–5 years at UoN, JKUAT, TUK\n"
            "• Registration with Engineers Board of Kenya (EBK)\n"
            "• Optional: MSc Process Engineering or Environmental Engineering"
        ),
        "job_opportunities": (
            "KPRL, Bidco, EABL, BAT Kenya, fertiliser companies, cement plants, "
            "pharmaceutical manufacturers, NEMA, research institutions"
        ),
        "future_outlook": (
            "Big Oil (Turkana basin), petrochemicals, and pharmaceutical manufacturing "
            "growth make chemical engineering one of Africa's most in-demand disciplines."
        ),
        "keywords": ["chemical engineering", "chemical technology", "petroleum engineering",
                     "process engineering", "materials engineering", "industrial chemistry"],
    },
    {
        "title": "Mining & Petroleum Engineer",
        "icon": "fas fa-hard-hat",
        "demand_level": "high",
        "average_salary": "KSh 100,000 – 400,000/month",
        "career_tags": "engineering,science",
        "description": (
            "Mining and petroleum engineers plan and supervise the extraction of minerals, oil, "
            "and gas from the earth. With Turkana oil and Kenya's mineral wealth, this field "
            "is growing rapidly."
        ),
        "duties": (
            "• Design mines and drilling operations\n"
            "• Supervise extraction of minerals and petroleum\n"
            "• Ensure worker safety in mines and oil fields\n"
            "• Assess mineral and oil reserves\n"
            "• Manage environmental impacts of extraction\n"
            "• Optimise production processes"
        ),
        "skills_required": (
            "• Geology, Physics, and Mathematics\n"
            "• Structural analysis and mine design\n"
            "• Health and safety management\n"
            "• GIS and remote sensing tools\n"
            "• Project management"
        ),
        "educational_pathway": (
            "• KCSE: B+ in Mathematics, Physics, Chemistry\n"
            "• BSc Mining Engineering or Petroleum Geoscience — 4–5 years\n"
            "• Registration with Engineers Board of Kenya (EBK)\n"
            "• Optional: MSc in Petroleum Engineering"
        ),
        "job_opportunities": (
            "Tullow Oil, Africa Oil Corp, Base Titanium, mining companies, Ministry of Petroleum, "
            "NEMA, geological surveys, engineering consultancies"
        ),
        "future_outlook": (
            "Kenya's Turkana oil fields and expanding mining sector (titanium, gold, soda ash) "
            "guarantee growing demand for mining and petroleum engineers."
        ),
        "keywords": ["mining engineering", "petroleum engineering", "geology", "geoscience",
                     "mineral processing", "extractive", "geo-informatics", "geomatic",
                     "earth science", "applied geology"],
    },
    {
        "title": "Quantity Surveyor",
        "icon": "fas fa-ruler-combined",
        "demand_level": "high",
        "average_salary": "KSh 60,000 – 200,000/month",
        "career_tags": "engineering,business,construction",
        "description": (
            "Quantity surveyors manage the costs and contracts of construction projects — "
            "from small buildings to major infrastructure. They ensure projects are delivered "
            "on budget and that contractors are paid fairly."
        ),
        "duties": (
            "• Prepare bills of quantities for construction projects\n"
            "• Estimate and monitor project costs\n"
            "• Manage procurement and contractor tendering\n"
            "• Value completed work and certify payments\n"
            "• Resolve contract disputes\n"
            "• Advise on cost control and value engineering"
        ),
        "skills_required": (
            "• Mathematics and numeracy\n"
            "• Knowledge of construction processes and materials\n"
            "• Negotiation and contract law understanding\n"
            "• Attention to detail\n"
            "• Project management skills"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above in Mathematics, Physics\n"
            "• BSc Quantity Surveying or Construction Management — 4 years at UoN, TUK, MUST\n"
            "• Membership with Institute of Quantity Surveyors of Kenya (IQSK)\n"
            "• Optional: MSc Project Management"
        ),
        "job_opportunities": (
            "Construction companies, government (KeNHA, KBC), property developers, "
            "engineering consultancies, World Bank/AfDB-funded projects, private practice"
        ),
        "future_outlook": (
            "Kenya's infrastructure boom (roads, affordable housing, airports) "
            "is creating sustained high demand for quantity surveyors."
        ),
        "keywords": ["quantity survey", "construction management", "building economics",
                     "real estate management", "building", "construction"],
    },
    {
        "title": "Land Surveyor & Geomatics Engineer",
        "icon": "fas fa-map-marked-alt",
        "demand_level": "high",
        "average_salary": "KSh 60,000 – 180,000/month",
        "career_tags": "engineering,science",
        "description": (
            "Land surveyors measure and map the physical features of the earth, determining "
            "property boundaries and supporting urban planning, construction, and land "
            "administration in Kenya."
        ),
        "duties": (
            "• Survey and map land parcels, roads, and utilities\n"
            "• Use GPS, total stations, and GIS software\n"
            "• Prepare cadastral maps and land registration documents\n"
            "• Provide topographic surveys for engineering projects\n"
            "• Handle boundary disputes with legal survey evidence\n"
            "• Conduct environmental and disaster risk mapping"
        ),
        "skills_required": (
            "• Mathematics and Geography\n"
            "• GIS and remote sensing software (ArcGIS, QGIS)\n"
            "• Precision and spatial reasoning\n"
            "• Knowledge of land laws in Kenya\n"
            "• Physical fitness for fieldwork"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above in Mathematics, Physics, Geography\n"
            "• BSc Geomatics or Land Surveying — 4 years at UoN, JKUAT, Moi\n"
            "• Registration with Institute of Surveyors of Kenya (ISK)\n"
            "• Licensed under the Survey Act (Kenya)"
        ),
        "job_opportunities": (
            "Ministry of Lands, National Land Commission, county governments, "
            "private surveying firms, construction companies, utility companies"
        ),
        "future_outlook": (
            "Kenya's land digitisation program, urban expansion, and Big Four housing "
            "agenda create strong sustained demand for surveyors."
        ),
        "keywords": ["surveying", "land survey", "geomatic", "geo-informatics", "geospatial",
                     "cartography", "remote sensing", "gis", "geographic information"],
    },
    {
        "title": "Telecommunications Engineer",
        "icon": "fas fa-broadcast-tower",
        "demand_level": "very_high",
        "average_salary": "KSh 80,000 – 280,000/month",
        "career_tags": "engineering,technology",
        "description": (
            "Telecommunications engineers design and maintain the networks — mobile, fibre, "
            "satellite — that connect Kenyans. With 5G rollout and fibre expansion, this is "
            "one of the fastest-growing engineering fields."
        ),
        "duties": (
            "• Design and deploy mobile and fixed network infrastructure\n"
            "• Manage and optimise network performance (4G, 5G, fibre)\n"
            "• Troubleshoot network outages and degradation\n"
            "• Plan spectrum allocation and frequency management\n"
            "• Integrate new technologies (IoT, satellite broadband)\n"
            "• Ensure network security and resilience"
        ),
        "skills_required": (
            "• Electronics and signal processing\n"
            "• Network protocols (TCP/IP, GSM, LTE)\n"
            "• RF engineering and antenna design\n"
            "• Project management\n"
            "• Problem-solving under operational pressure"
        ),
        "educational_pathway": (
            "• KCSE: B+ in Mathematics, Physics\n"
            "• BSc Telecommunication Engineering or Electronic Engineering — 4 years\n"
            "• Registration with Engineers Board of Kenya (EBK)\n"
            "• Certifications: CCNA, AWS, Huawei HCIA"
        ),
        "job_opportunities": (
            "Safaricom, Airtel, Telkom Kenya, Liquid Telecom, Kenya Power, "
            "CA Kenya, government, fibre infrastructure companies, consulting firms"
        ),
        "future_outlook": (
            "Kenya's ambition to become Africa's Silicon Savannah requires massive "
            "telecoms infrastructure investment, guaranteeing high demand."
        ),
        "keywords": ["telecommunication", "electronics engineering", "electronic", "communication engineering",
                     "wireless", "mobile communication", "signal processing"],
    },
    {
        "title": "Biomedical Engineer",
        "icon": "fas fa-heartbeat",
        "demand_level": "high",
        "average_salary": "KSh 60,000 – 200,000/month",
        "career_tags": "engineering,health,science",
        "description": (
            "Biomedical engineers develop and maintain medical equipment — from ventilators "
            "and X-ray machines to prosthetics and diagnostic devices — bridging engineering "
            "and healthcare to improve patient outcomes in Kenya."
        ),
        "duties": (
            "• Install, calibrate, and maintain medical equipment\n"
            "• Troubleshoot and repair hospital devices\n"
            "• Design biomedical devices and systems\n"
            "• Ensure equipment meets safety and regulatory standards\n"
            "• Train clinical staff on equipment use\n"
            "• Conduct technology assessment for hospital procurement"
        ),
        "skills_required": (
            "• Electronics, mechanics, and biology\n"
            "• Technical troubleshooting\n"
            "• Knowledge of medical device regulations\n"
            "• Communication with clinical teams\n"
            "• Project management for equipment procurement"
        ),
        "educational_pathway": (
            "• KCSE: B+ in Mathematics, Physics, Biology\n"
            "• BSc Biomedical Engineering — 4–5 years at JKUAT, UoN, Moi\n"
            "• Registration with Engineers Board of Kenya (EBK)\n"
            "• Optional: MSc Medical Engineering or Clinical Engineering"
        ),
        "job_opportunities": (
            "Government and private hospitals, medical device companies (GE Healthcare, Philips), "
            "Ministry of Health, NGOs, research institutions"
        ),
        "future_outlook": (
            "Kenya's Universal Health Coverage (UHC) plan is equipping thousands of public "
            "facilities — creating sustained demand for biomedical engineers."
        ),
        "keywords": ["biomedical", "biomedical engineering", "medical engineering", "clinical engineering",
                     "biotechnology", "biomechanics"],
    },
    # ── BUSINESS & FINANCE ───────────────────────────────────────────────────
    {
        "title": "Actuary",
        "icon": "fas fa-chart-line",
        "demand_level": "very_high",
        "average_salary": "KSh 120,000 – 500,000/month",
        "career_tags": "finance,mathematics,business",
        "description": (
            "Actuaries use mathematics and statistics to assess financial risks for insurance "
            "companies, pension funds, and banks. It is one of the highest-paying professions "
            "in Kenya with very few qualified practitioners."
        ),
        "duties": (
            "• Calculate insurance premiums and reserves\n"
            "• Model financial risks using statistical tools\n"
            "• Advise on pension fund management\n"
            "• Perform valuations for life and general insurance\n"
            "• Stress-test financial models for regulatory compliance\n"
            "• Present risk findings to board and regulators"
        ),
        "skills_required": (
            "• Outstanding mathematical and statistical ability\n"
            "• Proficiency in R, Python, or Excel (financial modelling)\n"
            "• Knowledge of financial markets\n"
            "• Communication and report-writing\n"
            "• Analytical and critical thinking"
        ),
        "educational_pathway": (
            "• KCSE: A or A- in Mathematics\n"
            "• BSc Actuarial Science — 4 years at UoN, Strathmore, Moi\n"
            "• Professional exams: Institute of Actuaries (IOA) or Society of Actuaries (SOA)\n"
            "• Fellow of the Actuarial Society of Kenya (FASK)"
        ),
        "job_opportunities": (
            "Insurance companies (Jubilee, Britam, APA), reinsurance firms, "
            "pension fund administrators, commercial banks, CBK, consulting firms"
        ),
        "future_outlook": (
            "Kenya has fewer than 300 fully qualified actuaries. Demand far exceeds supply "
            "and is growing with financial sector expansion and pension reforms."
        ),
        "keywords": ["actuarial", "actuarial science", "statistics", "applied statistics",
                     "financial mathematics", "risk management", "insurance"],
    },
    {
        "title": "Supply Chain & Logistics Manager",
        "icon": "fas fa-truck",
        "demand_level": "high",
        "average_salary": "KSh 60,000 – 200,000/month",
        "career_tags": "business,management",
        "description": (
            "Supply chain managers oversee the flow of goods from suppliers to customers — "
            "covering procurement, warehousing, transport, and distribution. Kenya's position "
            "as East Africa's trade hub makes this a high-demand field."
        ),
        "duties": (
            "• Source and evaluate suppliers and negotiate contracts\n"
            "• Manage warehouse operations and inventory\n"
            "• Coordinate transport and freight logistics\n"
            "• Track shipments and manage customs clearance\n"
            "• Optimise supply chain for cost and efficiency\n"
            "• Manage relationships with freight forwarders and clearing agents"
        ),
        "skills_required": (
            "• Procurement and contract management\n"
            "• ERP systems (SAP, Oracle, Microsoft Dynamics)\n"
            "• Negotiation and vendor management\n"
            "• Analytical and problem-solving skills\n"
            "• Knowledge of trade laws, Incoterms, and customs"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above\n"
            "• BSc Procurement & Supply Chain or Logistics Management — 4 years\n"
            "• CIPS (Chartered Institute of Procurement & Supply) certification\n"
            "• Optional: MSc Logistics and Supply Chain Management"
        ),
        "job_opportunities": (
            "Multinational companies, FMCG firms (Unilever, Nestlé), retailers, "
            "SGR / Kenya Railways, Mombasa Port, logistics companies, NGOs"
        ),
        "future_outlook": (
            "The SGR, LAPSSET corridor, and e-commerce growth are transforming Kenya's "
            "logistics sector and creating significant demand for supply chain professionals."
        ),
        "keywords": ["procurement", "supply chain", "logistics", "purchasing", "stores management",
                     "warehouse", "transport management", "shipping", "freight"],
    },
    {
        "title": "Real Estate & Property Manager",
        "icon": "fas fa-building",
        "demand_level": "high",
        "average_salary": "KSh 60,000 – 250,000/month",
        "career_tags": "business,finance,construction",
        "description": (
            "Real estate professionals value, manage, buy, sell, and develop property. "
            "Kenya's housing boom and rapid urbanisation are creating exceptional "
            "opportunities in this sector."
        ),
        "duties": (
            "• Value land and buildings using professional methodologies\n"
            "• Manage rental properties for landlords and investors\n"
            "• Facilitate property transactions and negotiations\n"
            "• Advise on real estate investment opportunities\n"
            "• Manage property development projects\n"
            "• Conduct feasibility studies and market analysis"
        ),
        "skills_required": (
            "• Valuation methods and real estate economics\n"
            "• Negotiation and sales skills\n"
            "• Knowledge of land laws and property acts in Kenya\n"
            "• Financial modelling and investment analysis\n"
            "• Communication and relationship management"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above in Mathematics\n"
            "• BSc Real Estate or Land Economics — 4 years at UoN, JKUAT, KU\n"
            "• Registration with Institute of Surveyors of Kenya (ISK)\n"
            "• Optional: MSc Real Estate or MBA"
        ),
        "job_opportunities": (
            "Property agencies, Knight Frank, HassConsult, real estate developers, "
            "banks (mortgage departments), county governments, NHC, private landlords"
        ),
        "future_outlook": (
            "Kenya needs 250,000 new homes per year. Government housing agenda and "
            "growing urban population ensure long-term demand for property professionals."
        ),
        "keywords": ["real estate", "land economics", "property management", "estate management",
                     "valuation", "urban planning", "urban and regional planning", "housing"],
    },
    # ── TOURISM & HOSPITALITY ────────────────────────────────────────────────
    {
        "title": "Tourism & Hospitality Manager",
        "icon": "fas fa-concierge-bell",
        "demand_level": "high",
        "average_salary": "KSh 50,000 – 200,000/month",
        "career_tags": "tourism,business,creative",
        "description": (
            "Tourism and hospitality managers run hotels, lodges, resorts, travel companies, "
            "and event venues. Kenya's world-class wildlife tourism makes this sector a major "
            "employer and foreign exchange earner."
        ),
        "duties": (
            "• Manage hotel or lodge operations (front office, F&B, housekeeping)\n"
            "• Develop marketing strategies to attract tourists\n"
            "• Ensure excellent guest experience and service quality\n"
            "• Manage budgets, revenue, and cost control\n"
            "• Train and supervise hospitality staff\n"
            "• Develop tour packages and itineraries"
        ),
        "skills_required": (
            "• Customer service excellence\n"
            "• Leadership and team management\n"
            "• Knowledge of tourism products and Kenyan tourism circuits\n"
            "• Financial management and budgeting\n"
            "• Languages (French, Chinese, German — value-add)"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above\n"
            "• BSc Tourism Management or Hotel Management — 4 years at KU, Moi, UoN\n"
            "• Diploma in Hospitality Management (TTIs)\n"
            "• Practical internship in a star-rated hotel"
        ),
        "job_opportunities": (
            "Sarova, Serena, Kempinski, Fairmont, Kenya Airways, travel agencies, "
            "safari companies, county tourism boards, MICE industry"
        ),
        "future_outlook": (
            "Kenya targets 5 million tourists annually. Recovery post-COVID and new "
            "tourism circuits (northern Kenya, coast) are driving hotel expansion."
        ),
        "keywords": ["tourism", "hospitality", "hotel management", "hotel and restaurant",
                     "travel and tourism", "ecotourism", "wildlife management", "tour operations",
                     "recreation", "leisure"],
    },
    {
        "title": "Chef & Culinary Professional",
        "icon": "fas fa-utensils",
        "demand_level": "high",
        "average_salary": "KSh 40,000 – 200,000/month",
        "career_tags": "tourism,creative,food",
        "description": (
            "Chefs and culinary professionals create food experiences in hotels, restaurants, "
            "airlines, and catering companies. Kenya's booming hospitality industry and "
            "growing middle class are creating strong demand for skilled culinary talent."
        ),
        "duties": (
            "• Plan menus and develop new recipes\n"
            "• Prepare and cook food to high quality standards\n"
            "• Manage kitchen staff and coordinate service\n"
            "• Control food costs and manage inventory\n"
            "• Ensure food safety and hygiene (HACCP)\n"
            "• Cater for large events and functions"
        ),
        "skills_required": (
            "• Culinary creativity and taste development\n"
            "• Kitchen management and leadership\n"
            "• Food safety and hygiene standards\n"
            "• Cost control and menu pricing\n"
            "• Physical stamina and team coordination"
        ),
        "educational_pathway": (
            "• KCSE: D+ or above\n"
            "• Certificate or Diploma in Culinary Arts / Food Production (TTIs, TVET)\n"
            "• BSc in Hospitality and Food Management\n"
            "• Attachment at a star-rated hotel or restaurant"
        ),
        "job_opportunities": (
            "5-star hotels, lodges, airlines, offshore oil vessels, catering companies, "
            "cruise ships, private households, restaurant chains, hospitals"
        ),
        "future_outlook": (
            "Tourism growth and global demand for Kenyan chefs (especially in Middle East "
            "and Europe) make culinary arts a career with excellent export opportunities."
        ),
        "keywords": ["culinary", "food production", "cookery", "catering", "food and beverage",
                     "pastry", "baking", "kitchen", "food service"],
    },
    # ── CREATIVE & MEDIA ─────────────────────────────────────────────────────
    {
        "title": "Film & Media Producer",
        "icon": "fas fa-film",
        "demand_level": "high",
        "average_salary": "KSh 50,000 – 300,000/month",
        "career_tags": "creative,media,technology",
        "description": (
            "Film and media producers create content for TV, film, online platforms, and "
            "advertising. Kenya's media industry is one of the most vibrant in Africa, "
            "with growing streaming and content creation markets."
        ),
        "duties": (
            "• Develop scripts, concepts, and story ideas\n"
            "• Manage film or TV production budgets and timelines\n"
            "• Direct on-set production and post-production\n"
            "• Edit video and audio content\n"
            "• Negotiate with broadcasters and distributors\n"
            "• Create digital content for YouTube, TikTok, Netflix Africa"
        ),
        "skills_required": (
            "• Creative storytelling and visual communication\n"
            "• Proficiency in editing software (Adobe Premiere, Final Cut Pro)\n"
            "• Project management and budgeting\n"
            "• Networking and pitching skills\n"
            "• Understanding of copyright and media laws"
        ),
        "educational_pathway": (
            "• KCSE: C or above\n"
            "• BSc Film and Television Production or Mass Communication — 4 years\n"
            "• Diploma in Film Production (TTIs)\n"
            "• Portfolio of produced work is essential"
        ),
        "job_opportunities": (
            "NTV, Citizen TV, K24, Netflix Africa, KBC, advertising agencies, "
            "independent production houses, content agencies, online platforms"
        ),
        "future_outlook": (
            "Africa's film industry (Nollywood, Swahiliwood) is growing rapidly. "
            "Netflix and Amazon's Africa push creates global opportunities for Kenyan creators."
        ),
        "keywords": ["film", "television", "media production", "broadcast", "mass communication",
                     "journalism", "communication", "media studies", "public relations",
                     "photography", "animation", "digital media"],
    },
    {
        "title": "Fashion Designer",
        "icon": "fas fa-tshirt",
        "demand_level": "medium",
        "average_salary": "KSh 30,000 – 150,000/month",
        "career_tags": "creative,business",
        "description": (
            "Fashion designers create clothing, accessories, and footwear, blending African "
            "aesthetics with global trends. Kenya's fashion industry is growing with designers "
            "gaining international recognition."
        ),
        "duties": (
            "• Sketch and design clothing and accessories\n"
            "• Select fabrics, colours, and embellishments\n"
            "• Create pattern templates and oversee garment production\n"
            "• Manage fashion collections and shows\n"
            "• Market and sell designs through boutiques and online\n"
            "• Study fashion trends and consumer preferences"
        ),
        "skills_required": (
            "• Drawing and visual creativity\n"
            "• Knowledge of fabrics and garment construction\n"
            "• Business and marketing skills\n"
            "• CAD design tools (CLO3D, Adobe Illustrator)\n"
            "• Tailoring and sewing skills"
        ),
        "educational_pathway": (
            "• KCSE: D+ or above\n"
            "• Certificate or Diploma in Fashion Design (TTIs, TVET)\n"
            "• BSc Fashion Design and Clothing Technology\n"
            "• Portfolio and internship with an established designer"
        ),
        "job_opportunities": (
            "Own label/brand, garment factories, fashion houses, textile companies, "
            "film and TV costume design, export fashion companies"
        ),
        "future_outlook": (
            "Africa's young, growing population and rising middle class make fashion "
            "an exciting growth sector. African print and sustainable fashion are global trends."
        ),
        "keywords": ["fashion", "garment", "clothing", "textile", "apparel", "fashion design",
                     "tailoring", "dressmaking", "knitting", "weaving", "leatherwork"],
    },
    {
        "title": "Interior Designer",
        "icon": "fas fa-couch",
        "demand_level": "medium",
        "average_salary": "KSh 40,000 – 200,000/month",
        "career_tags": "creative,engineering",
        "description": (
            "Interior designers create functional and aesthetically pleasing interior spaces "
            "for homes, offices, hotels, and commercial buildings. Kenya's construction boom "
            "is creating strong demand for interior design professionals."
        ),
        "duties": (
            "• Consult with clients to understand space needs and preferences\n"
            "• Develop space plans and design concepts\n"
            "• Select furniture, materials, lighting, and colour schemes\n"
            "• Prepare technical drawings and 3D visualisations\n"
            "• Manage contractors and suppliers during fit-out\n"
            "• Ensure designs comply with building codes and safety"
        ),
        "skills_required": (
            "• Creative visualisation and aesthetics\n"
            "• CAD software (AutoCAD, SketchUp, Revit)\n"
            "• Knowledge of materials and construction\n"
            "• Client management and presentation skills\n"
            "• Project management and budgeting"
        ),
        "educational_pathway": (
            "• KCSE: C or above\n"
            "• BSc Interior Design or Architecture (Interior Option)\n"
            "• Diploma in Interior Design (TTIs)\n"
            "• Portfolio of completed design projects"
        ),
        "job_opportunities": (
            "Interior design firms, architecture companies, hotels, corporate offices, "
            "furniture companies, real estate developers, self-employment"
        ),
        "future_outlook": (
            "Rapid office construction, hotel expansion, and growing demand for "
            "quality home design among Kenya's expanding middle class."
        ),
        "keywords": ["interior design", "interior architecture", "interior decoration",
                     "furniture", "space planning", "fine art", "visual arts"],
    },
    # ── EDUCATION ────────────────────────────────────────────────────────────
    {
        "title": "Early Childhood & Primary School Teacher",
        "icon": "fas fa-child",
        "demand_level": "very_high",
        "average_salary": "KSh 20,000 – 80,000/month",
        "career_tags": "education",
        "description": (
            "ECD and primary school teachers lay the educational foundation for young Kenyans. "
            "With 8-4-4 transitioning to CBC, teachers with competency-based curriculum "
            "training are especially in demand."
        ),
        "duties": (
            "• Plan and deliver lessons aligned to CBC curriculum\n"
            "• Assess and monitor children's learning and development\n"
            "• Create engaging and inclusive classroom environments\n"
            "• Communicate with parents and guardians\n"
            "• Participate in school management and co-curricular activities\n"
            "• Use digital learning tools and educational technology"
        ),
        "skills_required": (
            "• Child psychology and development knowledge\n"
            "• Patience, creativity, and enthusiasm for teaching\n"
            "• CBC curriculum competency\n"
            "• Classroom management\n"
            "• Communication and counselling skills"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above\n"
            "• Diploma in Early Childhood Development (ECD) — TTCs (2 years)\n"
            "• P1 Certificate for primary teaching\n"
            "• BEd Early Childhood or Primary Education — 4 years\n"
            "• TSC Registration"
        ),
        "job_opportunities": (
            "Public primary schools (TSC), private schools, nurseries, "
            "NGO education programs, UNICEF/Save the Children education projects"
        ),
        "future_outlook": (
            "CBC implementation requires mass retraining of existing teachers and "
            "hiring of ECD specialists. Government expansion of early learning centres (ELCs) "
            "will create thousands of new jobs."
        ),
        "keywords": ["early childhood", "ecd", "primary education", "teacher education",
                     "childhood development", "education (primary)", "junior secondary"],
    },
    {
        "title": "Special Needs & Inclusive Education Teacher",
        "icon": "fas fa-hands-helping",
        "demand_level": "very_high",
        "average_salary": "KSh 25,000 – 90,000/month",
        "career_tags": "education,social",
        "description": (
            "Special needs educators support learners with physical, intellectual, sensory, "
            "and learning disabilities, ensuring every Kenyan child gets quality education "
            "in line with the government's inclusive education policy."
        ),
        "duties": (
            "• Develop individual education plans (IEPs) for learners with disabilities\n"
            "• Use specialised teaching approaches (sign language, Braille, AAC)\n"
            "• Assess and identify learners with special needs\n"
            "• Coordinate with therapists, parents, and school management\n"
            "• Adapt curriculum and learning materials\n"
            "• Advocate for inclusive school environments"
        ),
        "skills_required": (
            "• Knowledge of disability categories and learning difficulties\n"
            "• Sign language and Braille literacy\n"
            "• Empathy, patience, and creativity\n"
            "• Behaviour management techniques\n"
            "• Collaboration with multi-disciplinary teams"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above\n"
            "• BEd Special Needs Education — 4 years at KU, UoN, Maseno\n"
            "• Diploma in Special Needs Education (TTCs)\n"
            "• TSC Registration"
        ),
        "job_opportunities": (
            "Government special schools, inclusive primary and secondary schools, "
            "NGOs (CBM, Light for the World), rehabilitation centres"
        ),
        "future_outlook": (
            "Kenya's ratification of the UN Convention on Rights of Persons with "
            "Disabilities and the Special Needs Education Policy will massively "
            "expand this sector."
        ),
        "keywords": ["special needs", "special education", "inclusive education",
                     "hearing impairment", "visual impairment", "sign language", "braille",
                     "disability studies"],
    },
    # ── PSYCHOLOGY & SOCIAL ──────────────────────────────────────────────────
    {
        "title": "Counseling Psychologist",
        "icon": "fas fa-brain",
        "demand_level": "high",
        "average_salary": "KSh 50,000 – 180,000/month",
        "career_tags": "health,social,education",
        "description": (
            "Counseling psychologists help individuals deal with mental health challenges, "
            "trauma, relationship issues, and life transitions. Mental health awareness in "
            "Kenya is growing rapidly, creating new opportunities."
        ),
        "duties": (
            "• Conduct individual, couple, family, and group therapy sessions\n"
            "• Administer psychological assessments and tests\n"
            "• Develop treatment plans for clients with mental health conditions\n"
            "• Provide crisis intervention and trauma counselling\n"
            "• Conduct psycho-education workshops in schools and workplaces\n"
            "• Keep case notes and refer severe cases to psychiatrists"
        ),
        "skills_required": (
            "• Empathy, active listening, and non-judgmental approach\n"
            "• Knowledge of counselling theories (CBT, DBT, person-centred)\n"
            "• Ethical practice and confidentiality\n"
            "• Report writing and case documentation\n"
            "• Resilience and emotional intelligence"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above\n"
            "• BA/BSc Psychology or Counselling Psychology — 4 years\n"
            "• MSc Counseling Psychology (required for full licensure)\n"
            "• Supervised practice (500+ hours)\n"
            "• Registration with Kenya Counsellors and Psychologists Association (KCPA)"
        ),
        "job_opportunities": (
            "Hospitals, schools and universities, private practice, corporates (EAP programs), "
            "NGOs, prisons, churches, military, national disaster response"
        ),
        "future_outlook": (
            "Growing awareness of mental health, post-COVID trauma, and workplace "
            "wellness programs are driving unprecedented demand for counsellors in Kenya."
        ),
        "keywords": ["psychology", "counselling", "counseling", "mental health",
                     "guidance and counselling", "social work", "psychosocial"],
    },
    {
        "title": "Urban & Regional Planner",
        "icon": "fas fa-city",
        "demand_level": "high",
        "average_salary": "KSh 60,000 – 200,000/month",
        "career_tags": "engineering,governance,environment",
        "description": (
            "Urban planners design cities, towns, and rural areas to be liveable, sustainable, "
            "and functional. As Kenya urbanises rapidly, planners are critical to managing "
            "growth in Nairobi and secondary cities."
        ),
        "duties": (
            "• Develop land use plans and zoning regulations\n"
            "• Design physical development plans for cities and counties\n"
            "• Assess environmental impact of development projects\n"
            "• Coordinate infrastructure planning (roads, water, sewers)\n"
            "• Engage communities in participatory planning\n"
            "• Review and approve building development applications"
        ),
        "skills_required": (
            "• Urban design and GIS/spatial planning tools\n"
            "• Knowledge of planning laws (Physical & Land Use Planning Act)\n"
            "• Analytical and research skills\n"
            "• Community engagement and stakeholder management\n"
            "• Project management"
        ),
        "educational_pathway": (
            "• KCSE: C+ or above in Geography, Mathematics\n"
            "• BSc Urban and Regional Planning — 4 years at UoN, JKUAT, Moi\n"
            "• Registration with Kenya Institute of Planners (KIP)\n"
            "• Optional: MSc Urban Planning or Environmental Planning"
        ),
        "job_opportunities": (
            "County governments, Ministry of Lands, Nairobi City County, "
            "NEMA, planning consultancies, World Bank, UN-Habitat"
        ),
        "future_outlook": (
            "Nairobi's population will double by 2040. Kenya needs thousands of "
            "planners to manage urbanisation sustainably."
        ),
        "keywords": ["urban planning", "urban and regional planning", "regional planning",
                     "physical planning", "town planning", "urban design", "spatial planning",
                     "community development", "housing and urban development"],
    },
    # ── AGRICULTURE & NATURAL RESOURCES ──────────────────────────────────────
    {
        "title": "Food Scientist & Technologist",
        "icon": "fas fa-seedling",
        "demand_level": "high",
        "average_salary": "KSh 50,000 – 150,000/month",
        "career_tags": "science,food,agriculture",
        "description": (
            "Food scientists develop, process, preserve, and improve food products for "
            "human consumption. Kenya's growing food processing industry (Unga, Bidco, Kenchic) "
            "offers excellent career opportunities."
        ),
        "duties": (
            "• Develop new food products and improve existing ones\n"
            "• Conduct quality control and food safety audits\n"
            "• Analyse food for nutritional content and contaminants\n"
            "• Manage HACCP and food safety management systems\n"
            "• Research new preservation and packaging technologies\n"
            "• Ensure compliance with KEBS and international food standards"
        ),
        "skills_required": (
            "• Chemistry, Biology, and Microbiology\n"
            "• Laboratory skills and analytical techniques\n"
            "• Knowledge of food laws and KEBS standards\n"
            "• Attention to detail and quality consciousness\n"
            "• Research and innovation skills"
        ),
        "educational_pathway": (
            "• KCSE: B or above in Chemistry, Biology\n"
            "• BSc Food Science and Technology — 4 years at UoN, JKUAT, Egerton\n"
            "• Optional: MSc Food Processing or Food Safety\n"
            "• Certification in HACCP and Food Safety Management"
        ),
        "job_opportunities": (
            "Unga Group, Bidco, KCC, Del Monte, Kenchic, KEBS, KEPHIS, "
            "food banks, research institutions, tea and coffee companies"
        ),
        "future_outlook": (
            "Kenya's food processing sector is growing at 8% annually. Value addition "
            "agenda and export markets create strong demand for food scientists."
        ),
        "keywords": ["food science", "food technology", "food processing", "food safety",
                     "food and nutrition", "dairy technology", "dairy science", "meat science",
                     "post-harvest", "agricultural processing"],
    },
    {
        "title": "Livestock & Animal Husbandry Specialist",
        "icon": "fas fa-horse",
        "demand_level": "high",
        "average_salary": "KSh 40,000 – 120,000/month",
        "career_tags": "agriculture,science",
        "description": (
            "Animal husbandry specialists improve livestock productivity for meat, milk, "
            "eggs, and hides. With dairy and poultry being major sectors, this is a "
            "high-impact career for Kenya's food security."
        ),
        "duties": (
            "• Advise farmers on livestock breeds, feeding, and management\n"
            "• Implement animal health and vaccination programs\n"
            "• Manage breeding programs to improve stock quality\n"
            "• Conduct farm assessments and productivity analysis\n"
            "• Train farmers on modern animal husbandry practices\n"
            "• Support value addition in dairy, poultry, and beef production"
        ),
        "skills_required": (
            "• Animal science and husbandry knowledge\n"
            "• Practical skills in livestock management\n"
            "• Communication and extension training skills\n"
            "• Business skills for farm economics\n"
            "• Veterinary first-aid knowledge"
        ),
        "educational_pathway": (
            "• KCSE: C or above in Biology\n"
            "• Diploma in Animal Production (TVET — 2–3 years)\n"
            "• BSc Animal Science or Range Management — 4 years at Egerton, UoN, KAU\n"
            "• Optional: MSc Animal Breeding and Genetics"
        ),
        "job_opportunities": (
            "Ministry of Agriculture, county government extension services, "
            "dairy companies (KCC, Brookside), large ranches, NGOs, Kenya Meat Commission"
        ),
        "future_outlook": (
            "Rising demand for protein and dairy products plus climate-resilient livestock "
            "programs make this sector essential to Kenya's food security agenda."
        ),
        "keywords": ["animal production", "animal husbandry", "livestock", "range management",
                     "animal science", "dairy", "poultry", "pasture", "range and forestry"],
    },
    {
        "title": "Forestry & Natural Resources Officer",
        "icon": "fas fa-tree",
        "demand_level": "medium",
        "average_salary": "KSh 40,000 – 110,000/month",
        "career_tags": "environment,agriculture,science",
        "description": (
            "Forestry officers manage Kenya's forests and natural ecosystems, combating "
            "deforestation, promoting reforestation, and conserving biodiversity. "
            "Kenya aims to achieve 10% forest cover — driving demand."
        ),
        "duties": (
            "• Survey and manage forest resources\n"
            "• Develop and implement forest management plans\n"
            "• Combat illegal logging and encroachment\n"
            "• Conduct community forestry and agroforestry programs\n"
            "• Manage carbon credit and REDD+ projects\n"
            "• Monitor wildlife and ecosystem health"
        ),
        "skills_required": (
            "• Ecology and conservation biology\n"
            "• GIS and remote sensing for forest mapping\n"
            "• Community mobilisation and extension\n"
            "• Law enforcement and patrol skills\n"
            "• Report writing and data collection"
        ),
        "educational_pathway": (
            "• KCSE: C or above in Biology, Geography\n"
            "• Diploma in Forestry (TVET — 2–3 years)\n"
            "• BSc Forestry or Natural Resource Management — 4 years\n"
            "• Optional: MSc Forest Policy or Conservation"
        ),
        "job_opportunities": (
            "Kenya Forest Service (KFS), KWS, NEMA, county governments, "
            "NGOs (WWF, IUCN), international carbon markets, tour operators"
        ),
        "future_outlook": (
            "Climate change mitigation, carbon credits, and government reforestation "
            "targets ensure growing demand for forestry professionals."
        ),
        "keywords": ["forestry", "natural resource", "conservation", "wildlife", "ecology",
                     "environmental science", "agroforestry", "range", "environmental management"],
    },
    {
        "title": "Fisheries & Aquaculture Officer",
        "icon": "fas fa-fish",
        "demand_level": "medium",
        "average_salary": "KSh 35,000 – 100,000/month",
        "career_tags": "agriculture,science,environment",
        "description": (
            "Fisheries officers manage Kenya's aquatic resources including Lake Victoria, "
            "the Indian Ocean coastline, and inland fish farms. Aquaculture is a fast-growing "
            "sector under the Big Four Agenda."
        ),
        "duties": (
            "• Monitor fish populations and aquatic ecosystems\n"
            "• Enforce fisheries regulations and licensing\n"
            "• Train and advise fish farmers on aquaculture practices\n"
            "• Manage fish hatcheries and fingerling production\n"
            "• Conduct fish quality control and value addition\n"
            "• Research on fish breeding and disease management"
        ),
        "skills_required": (
            "• Aquatic biology and ecology\n"
            "• Fish farming (pond, cage, and recirculating systems)\n"
            "• Data collection and fisheries surveys\n"
            "• Extension and community mobilisation\n"
            "• Laboratory skills for fish health testing"
        ),
        "educational_pathway": (
            "• KCSE: C or above in Biology\n"
            "• Diploma in Fisheries Management (TVET)\n"
            "• BSc Fisheries and Aquatic Sciences — 4 years at UoN, Maseno, Pwani\n"
            "• Optional: MSc Aquaculture"
        ),
        "job_opportunities": (
            "State Department of Fisheries, county fisheries departments, "
            "KenFish, commercial fish farms, export fish processing plants, NGOs"
        ),
        "future_outlook": (
            "Kenya imports fish despite its long coastline and lakes. "
            "Aquaculture growth and Blue Economy investments create major opportunities."
        ),
        "keywords": ["fisheries", "aquaculture", "aquatic", "marine", "oceanography",
                     "fish", "blue economy", "coastal"],
    },
    {
        "title": "Agricultural Extension Officer",
        "icon": "fas fa-tractor",
        "demand_level": "high",
        "average_salary": "KSh 35,000 – 100,000/month",
        "career_tags": "agriculture,education",
        "description": (
            "Agricultural extension officers bridge scientific research and farming practice, "
            "training farmers on modern, climate-smart agricultural techniques to improve "
            "food security and income."
        ),
        "duties": (
            "• Train farmers on improved seeds, fertilisers, and cultivation methods\n"
            "• Demonstrate pest and disease management\n"
            "• Introduce farmers to modern irrigation and water harvesting\n"
            "• Facilitate farmer group formation and cooperative development\n"
            "• Collect agricultural data for county planning\n"
            "• Link farmers to markets and agribusiness buyers"
        ),
        "skills_required": (
            "• Agronomy and crop science knowledge\n"
            "• Communication and training facilitation\n"
            "• Local language proficiency\n"
            "• Ability to work in rural, remote areas\n"
            "• Basic ICT for digital extension (e-Extension)"
        ),
        "educational_pathway": (
            "• KCSE: C or above in Biology\n"
            "• Diploma in Agriculture (TVET — 2–3 years)\n"
            "• BSc Agricultural Education and Extension — 4 years\n"
            "• Optional: MSc Extension Education"
        ),
        "job_opportunities": (
            "County agriculture departments, Ministry of Agriculture, NGOs, "
            "fertiliser and seed companies (Dawa), AGRA, KALRO, SACCO agri-programs"
        ),
        "future_outlook": (
            "Digital extension platforms and climate-smart agriculture programs "
            "are creating new demand for extension officers with digital literacy."
        ),
        "keywords": ["agriculture", "agricultural", "agronomy", "crop science", "agribusiness",
                     "horticulture", "plant science", "soil science", "irrigation",
                     "agricultural extension", "farm management"],
    },
    # ── TECHNICAL / ARTISAN ───────────────────────────────────────────────────
    {
        "title": "Electrician & Electrical Technician",
        "icon": "fas fa-bolt",
        "demand_level": "very_high",
        "average_salary": "KSh 30,000 – 120,000/month",
        "career_tags": "engineering,technology",
        "description": (
            "Electricians install, maintain, and repair electrical systems in buildings, "
            "factories, and infrastructure. Kenya's rural electrification program and "
            "housing boom are creating massive demand for trained electrical technicians."
        ),
        "duties": (
            "• Install electrical wiring, outlets, and distribution boards\n"
            "• Repair and maintain electrical equipment and machinery\n"
            "• Connect buildings to Kenya Power grid\n"
            "• Install solar photovoltaic (PV) systems\n"
            "• Diagnose and fix electrical faults\n"
            "• Ensure compliance with wiring regulations and safety standards"
        ),
        "skills_required": (
            "• Electrical theory and circuit analysis\n"
            "• Practical wiring and installation skills\n"
            "• Safety-first mindset (working with live systems)\n"
            "• Reading of electrical drawings and schematics\n"
            "• Basic mathematics and problem-solving"
        ),
        "educational_pathway": (
            "• KCSE: D+ or above in Mathematics, Physics\n"
            "• Certificate in Electrical Installation (TVET — 1–2 years)\n"
            "• Craft Certificate or Diploma in Electrical Engineering (TVET)\n"
            "• Trade Test registration with NITA\n"
            "• Optional: HND Electrical Engineering"
        ),
        "job_opportunities": (
            "Kenya Power, Stima Sacco, rural electrification contractors, "
            "construction companies, factories, solar companies, self-employment"
        ),
        "future_outlook": (
            "Last-Mile Connectivity program and rapid construction growth ensure "
            "decades of demand for qualified electricians. Solar and EV charging "
            "are creating new specialisations."
        ),
        "keywords": ["electrical installation", "electrical engineering", "power engineering",
                     "electrical technology", "electronics", "solar", "renewable energy",
                     "electrical and electronic"],
    },
    {
        "title": "Automotive Technician (Mechanic)",
        "icon": "fas fa-car",
        "demand_level": "very_high",
        "average_salary": "KSh 25,000 – 100,000/month",
        "career_tags": "engineering,technology",
        "description": (
            "Automotive technicians diagnose, repair, and service vehicles — from cars and "
            "trucks to motorcycles and farm machinery. Kenya's growing vehicle fleet and "
            "motorcycle boda-boda industry create strong demand."
        ),
        "duties": (
            "• Diagnose mechanical and electrical vehicle faults\n"
            "• Service engines, brakes, suspension, and transmission\n"
            "• Use diagnostic computers for modern vehicle systems\n"
            "• Repair and replace auto parts and components\n"
            "• Service motorcycles, tractors, and heavy machinery\n"
            "• Manage workshop operations and customer relations"
        ),
        "skills_required": (
            "• Mechanical aptitude and hand-eye coordination\n"
            "• Diagnostic tool proficiency\n"
            "• Knowledge of engine and vehicle systems\n"
            "• Physical fitness for manual work\n"
            "• Customer service and communication"
        ),
        "educational_pathway": (
            "• KCSE: D+ or above in Mathematics, Physics\n"
            "• Certificate in Automotive Engineering (TVET — 1–2 years)\n"
            "• Craft or Diploma in Motor Vehicle Mechanics (TVET)\n"
            "• Trade Test certification with NITA"
        ),
        "job_opportunities": (
            "Vehicle dealerships, auto garages, boda-boda workshops, transport companies, "
            "manufacturing plants, NTSA, Kenya Defence Forces, self-employment"
        ),
        "future_outlook": (
            "Kenya's fleet of 2 million+ vehicles and millions of motorcycles require "
            "constant maintenance. Electric vehicle (EV) servicing is an emerging specialisation."
        ),
        "keywords": ["automotive", "motor vehicle", "mechanical engineering", "motor mechanics",
                     "vehicle", "automobile", "diesel plant", "plant mechanics", "tractor"],
    },
    {
        "title": "Building & Construction Technician",
        "icon": "fas fa-hard-hat",
        "demand_level": "very_high",
        "average_salary": "KSh 30,000 – 120,000/month",
        "career_tags": "engineering,construction",
        "description": (
            "Building technicians execute construction projects — from laying foundations "
            "to finishing walls, roofs, and floors. Kenya's affordable housing agenda and "
            "infrastructure boom create vast employment."
        ),
        "duties": (
            "• Read and interpret construction drawings and specifications\n"
            "• Lay foundations, brickwork, and concrete structures\n"
            "• Apply plaster, screeds, tiles, and finishes\n"
            "• Install doors, windows, and roofing\n"
            "• Supervise site workers and sub-contractors\n"
            "• Ensure construction quality and safety on site"
        ),
        "skills_required": (
            "• Construction methods and materials knowledge\n"
            "• Blueprint reading and technical drawing\n"
            "• Site supervision and quality control\n"
            "• Physical fitness for manual site work\n"
            "• Basic maths for measurements and quantities"
        ),
        "educational_pathway": (
            "• KCSE: D+ or above in Mathematics\n"
            "• Certificate in Building Construction (TVET — 1–2 years)\n"
            "• Craft or Diploma in Building and Civil Engineering (TVET)\n"
            "• Trade Test certification with NITA"
        ),
        "job_opportunities": (
            "Construction companies, government infrastructure projects, "
            "real estate developers, private building contractors, self-employment"
        ),
        "future_outlook": (
            "Government's 500,000 affordable homes target, KeRRA road projects, "
            "and county infrastructure programs ensure decades of demand."
        ),
        "keywords": ["building construction", "building technology", "civil engineering technology",
                     "masonry", "carpentry", "plumbing", "architecture technology", "construction",
                     "brickwork", "plastering", "tiling"],
    },
    {
        "title": "Welder & Metal Fabricator",
        "icon": "fas fa-fire",
        "demand_level": "high",
        "average_salary": "KSh 25,000 – 100,000/month",
        "career_tags": "engineering,technology",
        "description": (
            "Welders join metals to construct and repair structures, pipelines, machinery, "
            "and vehicles. As Kenya industrialises, skilled welders are critical across "
            "manufacturing, construction, and infrastructure sectors."
        ),
        "duties": (
            "• Weld metals using MIG, TIG, arc, and gas techniques\n"
            "• Fabricate metal structures, frames, and equipment\n"
            "• Read engineering drawings for fabrication specifications\n"
            "• Inspect and test weld quality\n"
            "• Repair machinery, pipelines, and structures\n"
            "• Operate cutting, bending, and forming equipment"
        ),
        "skills_required": (
            "• Welding technique proficiency (MIG, TIG, SMAW)\n"
            "• Metal properties and heat treatment knowledge\n"
            "• Technical drawing interpretation\n"
            "• Safety in use of welding equipment\n"
            "• Physical endurance and precision"
        ),
        "educational_pathway": (
            "• KCSE: D+ or above\n"
            "• Certificate in Welding and Fabrication (TVET — 1–2 years)\n"
            "• Craft or Diploma in Mechanical Engineering (Fabrication) (TVET)\n"
            "• Trade Test certification with NITA"
        ),
        "job_opportunities": (
            "Manufacturing plants, shipyards, construction companies, "
            "pipeline companies, government engineering workshops, self-employment"
        ),
        "future_outlook": (
            "SGR maintenance, pipeline infrastructure (LAPSSET), manufacturing growth, "
            "and industrial parks guarantee strong demand for welders and fabricators."
        ),
        "keywords": ["welding", "fabrication", "metal work", "metalwork", "sheet metal",
                     "blacksmith", "boilermaking", "fitter", "mechanical technology"],
    },
    # ── TECHNOLOGY ────────────────────────────────────────────────────────────
    {
        "title": "Cloud & DevOps Engineer",
        "icon": "fas fa-cloud",
        "demand_level": "very_high",
        "average_salary": "KSh 100,000 – 400,000/month",
        "career_tags": "technology,engineering",
        "description": (
            "Cloud and DevOps engineers build, automate, and maintain the infrastructure "
            "that runs modern software. With companies moving to AWS, GCP, and Azure, "
            "this is among the highest-paying tech roles in Kenya."
        ),
        "duties": (
            "• Design and manage cloud infrastructure (AWS, Azure, GCP)\n"
            "• Build CI/CD pipelines for software deployment\n"
            "• Automate server configuration and scaling with IaC (Terraform)\n"
            "• Monitor system performance and incident response\n"
            "• Implement container orchestration (Docker, Kubernetes)\n"
            "• Ensure cloud security and cost optimisation"
        ),
        "skills_required": (
            "• Linux systems administration\n"
            "• Cloud platforms (AWS, GCP, Azure)\n"
            "• Scripting (Bash, Python)\n"
            "• Docker and Kubernetes\n"
            "• CI/CD tools (Jenkins, GitHub Actions)"
        ),
        "educational_pathway": (
            "• KCSE: B or above in Mathematics\n"
            "• BSc Computer Science, IT, or Software Engineering — 4 years\n"
            "• Cloud certifications: AWS Solutions Architect, GCP Professional, Azure Administrator\n"
            "• Kubernetes (CKA) and Terraform certifications"
        ),
        "job_opportunities": (
            "Safaricom, Equity Bank, Andela, Twiga Foods, M-PESA Africa, "
            "multinational tech companies (remote), cloud consulting firms"
        ),
        "future_outlook": (
            "Every company is moving to cloud. Kenya's fintech and startup boom "
            "make DevOps and cloud engineers among the most in-demand tech roles."
        ),
        "keywords": ["computer science", "information technology", "software engineering",
                     "information systems", "computing", "data science", "artificial intelligence",
                     "cloud", "cyber", "network", "it security", "computer network"],
    },
    {
        "title": "Digital Marketer & Growth Specialist",
        "icon": "fas fa-bullhorn",
        "demand_level": "very_high",
        "average_salary": "KSh 50,000 – 250,000/month",
        "career_tags": "business,technology,creative,media",
        "description": (
            "Digital marketers drive business growth through online channels — social media, "
            "search engines, email, and content. Every business in Kenya now needs digital "
            "marketing to reach connected consumers."
        ),
        "duties": (
            "• Manage social media accounts and community engagement\n"
            "• Plan and execute paid advertising campaigns (Google, Meta, TikTok)\n"
            "• Create and optimise content for SEO\n"
            "• Analyse campaign performance with Google Analytics and data tools\n"
            "• Manage email marketing and customer retention\n"
            "• Develop brand strategy and online identity"
        ),
        "skills_required": (
            "• Social media platforms expertise\n"
            "• Google Ads, Meta Ads, and SEO skills\n"
            "• Copywriting and visual content creation\n"
            "• Analytics and data interpretation\n"
            "• Marketing strategy and brand management"
        ),
        "educational_pathway": (
            "• KCSE: C or above\n"
            "• BSc Marketing, Communications, or Digital Media — 4 years\n"
            "• Google, Meta, and HubSpot digital marketing certifications\n"
            "• Portfolio of campaigns managed"
        ),
        "job_opportunities": (
            "Agencies, e-commerce companies, banks, telcos, startups, NGOs, "
            "media houses, and freelancing for international clients"
        ),
        "future_outlook": (
            "Kenya has 22+ million internet users and a booming e-commerce market. "
            "Every brand needs skilled digital marketers — this field is only growing."
        ),
        "keywords": ["marketing", "digital marketing", "advertising", "public relations",
                     "communication", "media", "journalism", "brand management",
                     "business administration", "commerce"],
    },
]

# ── Course keyword mappings for ALL profiles (existing + new) ────────────────
# Format: {profile_title: [keyword1, keyword2, ...]}
# Django will match courses where name icontains any keyword.
# Allowed course types — only high-quality, career-relevant programmes
ALLOWED_COURSE_TYPES = [
    "Degree",
    "TVET Diploma (Level 6)",
    "TVET Certificate (Level 5)",
    "KMTC",
]

# ── Precise keyword map ──────────────────────────────────────────────────────
# Rules:
#  - Keywords must be SPECIFIC enough not to match unrelated careers
#  - Each keyword is matched case-insensitively against course.name
#  - Only courses with ALLOWED_COURSE_TYPES are linked (Artisan L4, Craft L3,
#    Trade Tests, TTC, Short Course, Proficiency are excluded)
# ─────────────────────────────────────────────────────────────────────────────
COURSE_KEYWORD_MAP = {
    # ── HEALTH ───────────────────────────────────────────────────────────────
    # Only MBChB — use "and bachelor of surgery" to exclude "veterinary medicine and surgery"
    "Medical Doctor (Physician)": [
        "medicine and bachelor of surgery",
        "medicine & bachelor of surgery",
        "mbchb",
        "m.b.ch.b",
    ],
    "Registered Nurse": [
        "nursing",
        "nurse",
        "midwifery",
    ],
    "Clinical Officer": [
        "clinical officer",
        "clinical medicine",
    ],
    "Pharmacist": [
        "pharmacy",
        "pharmaceutical",
    ],
    "Veterinarian": [
        # Only proper veterinary degrees/diplomas — NOT animal science or zoology
        "veterinary",
        "veterinary medicine",
    ],
    "Dental Surgeon": [
        "dental",
        "dentistry",
        "oral health",
    ],
    "Physiotherapist": [
        "physiotherapy",
        "physical therapy",
        "occupational therapy",
    ],
    "Nutritionist & Dietitian": [
        # Specific nutrition/dietetics — NOT generic food science/technology
        # Avoid "food nutrition" alone as it catches teacher training diplomas
        "nutrition and dietetics",
        "human nutrition",
        "nutraceutical",
        "community nutrition",
        "dietetics management",
    ],
    "Medical Laboratory Technologist": [
        "medical laboratory",
        "laboratory sciences",
        "laboratory technology",
        "clinical biochemistry",
        "haematology",
        "pathology",
        "medical microbiology",
    ],
    "Radiographer": [
        "radiography",
        "medical imaging",
        "radiology",
        "diagnostic imaging",
    ],
    "Optometrist": [
        "optometry",
        "vision science",
        "applied optics",
    ],
    "Public Health Officer": [
        # Specific public/community health — NOT animal health or general health IT
        "public health",
        "environmental health",
        "epidemiology",
        "community health",
        "health promotion",
        "population health",
    ],
    "Biochemist": [
        "biochemistry",
        "molecular biology",
        "biochemical",
    ],

    # ── ENGINEERING ──────────────────────────────────────────────────────────
    "Civil Engineer": [
        "civil engineering",
        "structural engineering",
        "civil and structural",
    ],
    "Electrical Engineer": [
        "electrical engineering",
        "electrical and electronic engineering",
        "electrical and electronics engineering",
        "power engineering",
    ],
    "Mechanical Engineer": [
        "mechanical engineering",
        "mechanical and production",
        "mechanical and industrial",
        "manufacturing engineering",
    ],
    "Agricultural Engineer": [
        "agricultural engineering",
        "agricultural mechanisation",
        "biosystems engineering",
        "irrigation engineering",
    ],
    "Chemical Engineer": [
        "chemical engineering",
        "chemical and process",
        "industrial chemistry",
        "process engineering",
    ],
    "Mining & Petroleum Engineer": [
        # Specific mining/petroleum — NOT geomatic (surveying) or geo-informatics
        "mining engineering",
        "petroleum engineering",
        "mineral processing",
        "mining and mineral",
        "petroleum chemistry",
        "petroleum geoscience",
        "earth science",
        "geology",
    ],
    "Biomedical Engineer": [
        # Only proper biomedical engineering — NOT agricultural biotechnology
        "biomedical engineering",
        "biomedical science",
        "medical engineering",
    ],
    "Telecommunications Engineer": [
        "telecommunication",
        "telecommunication and information",
        "electrical and telecommunication",
        "communication engineering",
        "electronics engineering",
        "wireless communication",
    ],
    "Quantity Surveyor": [
        "quantity survey",
        "quantity surveying",
        "construction management",
        "building economics",
        # NOTE: real estate management removed — belongs to Real Estate profile
    ],
    "Land Surveyor & Geomatics Engineer": [
        # Specific geospatial/surveying — NOT "surveying" alone (matches quantity survey)
        "land survey",
        "geomatic engineering",
        "geospatial engineering",
        "geospatial information",
        "geomatics and geospatial",
        "remote sensing",
        "geographic information",
        "cartography",
        "surveying technology",
    ],
    "Architect": [
        "architecture",
        "architectural studies",
    ],
    "Environmental Scientist": [
        "environmental science",
        "environmental studies",
        "environmental management",
        "environmental conservation",
    ],

    # ── TECHNOLOGY ───────────────────────────────────────────────────────────
    "Software Developer": [
        # Specific software/CS degrees — NOT geo-informatics or health IT records
        "software engineering",
        "computer science",
        "software development",
        "computing",
        "applied computer science",
        "artificial intelligence",
        "machine learning",
    ],
    "Data Scientist": [
        # Specific data/statistics — NOT library science (information science)
        "data science",
        "applied statistics",
        "actuarial science",
        "data analytics",
        "big data",
        "machine learning",
        "artificial intelligence",
        "statistics and information technology",
    ],
    "Cybersecurity Analyst": [
        "cybersecurity",
        "cyber security",
        "information security",
        "computer security",
        "network security",
        "information assurance",
    ],
    "Network Engineer": [
        # Specific networking — NOT general IT (avoids health records IT matches)
        "computer networks",
        "network engineering",
        "information technology",  # kept for general IT networking degrees
        "business information technology",
        "information systems",
    ],
    "Cloud & DevOps Engineer": [
        "computer science",
        "software engineering",
        "cloud computing",
        "computing",
        "information technology",
        "information systems",
        "cyber security",
        "data science",
    ],
    "Digital Marketer & Growth Specialist": [
        # Specific digital marketing — NOT journalism, PR, or media studies
        "marketing",
        "digital marketing",
        "sales and marketing",
        "business administration in marketing",
        "advertising",
    ],

    # ── BUSINESS & FINANCE ───────────────────────────────────────────────────
    "Accountant (CPA)": [
        "accounting",
        "accountancy",
        "accounts and finance",
        "accounting and finance",
        "financial management",
    ],
    "Banker & Financial Analyst": [
        "banking",
        "financial economics",
        "financial engineering",
        "bachelor of finance",
        "science in finance",
        "investment",
        "economics and finance",
    ],
    "Economist": [
        "economics",
        "development economics",
        "agricultural economics",
        "applied economics",
    ],
    "Actuary": [
        # Specific actuarial/statistics — NOT general statistics alone
        "actuarial science",
        "actuarial",
        "financial mathematics",
        "applied statistics",
    ],
    "Supply Chain & Logistics Manager": [
        "procurement",
        "supply chain",
        "logistics",
        "purchasing and supplies",
        "purchasing and supply",
        "purchasing and logistics",
        "stores management",
        "transport management",
    ],
    "Real Estate & Property Manager": [
        "real estate",
        "land economics",
        "property management",
        "estate management",
        "real estate management",
    ],
    "Human Resource Manager": [
        "human resource",
        "human resources",
        "industrial relations",
    ],
    "Marketing & Sales Professional": [
        # Specific marketing — NOT all BBA (too broad)
        "marketing",
        "sales and marketing",
        "business administration in marketing",
    ],

    # ── LAW & GOVERNANCE ─────────────────────────────────────────────────────
    "Advocate / Lawyer": [
        # Only proper law degrees — NOT wildlife law enforcement TVET
        "bachelor of laws",
        "llb",
        "jurisprudence",
    ],
    "Public Administrator": [
        "public administration",
        "public policy",
        "political science",
        "governance",
        "public management",
    ],

    # ── EDUCATION ────────────────────────────────────────────────────────────
    "Secondary School Teacher": [
        "bachelor of education",
        "bachelor of arts (with education)",
        "arts with education",
        "science with education",
        "mathematics with education",
        "teacher education",
        "education (arts)",
        "education (science)",
        "education technology",
    ],
    "Early Childhood & Primary School Teacher": [
        "early childhood",
        "ecd",
        "childhood development",
        "primary education",
        "early childhood education",
        "early childhood development",
    ],
    "Special Needs & Inclusive Education Teacher": [
        "special needs education",
        "special needs",
        "special education",
        "inclusive education",
        "hearing impairment",
        "visual impairment",
    ],

    # ── SOCIAL SCIENCES ──────────────────────────────────────────────────────
    "Social Worker": [
        "social work",
        "community development",
        "sociology",
        "development studies",
        "gender and development",
    ],
    "Counseling Psychologist": [
        "psychology",
        "counselling",
        "counseling",
        "guidance and counselling",
        "mental health",
    ],
    "Urban & Regional Planner": [
        # Specific urban planning — NOT community development (social work)
        "urban and regional planning",
        "urban planning",
        "regional planning",
        "physical planning",
        "town planning",
        "urban design",
        "spatial planning",
        "housing and urban",
    ],
    "Journalist & Media Personality": [
        "journalism",
        "mass communication",
        "broadcasting",
        "digital journalism",
        "broadcast journalism",
        "communication and media",
        "communication studies",
        "media studies",
        "applied communication",
    ],

    # ── CREATIVE ─────────────────────────────────────────────────────────────
    "Graphic Designer & Creative Director": [
        # Specific design/animation — NOT journalism "digital media" or teacher fine art
        "graphic design",
        "visual communication",
        "animation and graphics",
        "animation",
        "creative arts",
        "graphic communication",
    ],
    "Film & Media Producer": [
        "film",
        "television",
        "media production",
        "broadcast",
        "mass communication",
        "performing arts and film",
        "theatre arts",
        "arts in journalism",
        "journalism and mass",
        "journalism and digital",
    ],
    "Fashion Designer": [
        "fashion design",
        "fashion and apparel",
        "apparel and fashion",
        "clothing technology",
        "textile and fashion",
        "textile technology",
        "dressmaking",
        "garment",
        "leatherwork",
    ],
    "Interior Designer": [
        # Specific interior design — NOT fine art teacher training
        "interior design",
        "interior architecture",
        "clothing textile and interior",
    ],

    # ── TOURISM & HOSPITALITY ────────────────────────────────────────────────
    "Tourism & Hospitality Manager": [
        # Remove "recreation" — matched PE education degrees
        "tourism",
        "hospitality",
        "hotel management",
        "hotel and hospitality",
        "travel and tourism",
        "ecotourism",
        "tour operations",
        "catering and hospitality",
        "hotels and hospitality",
    ],
    "Chef & Culinary Professional": [
        "culinary",
        "food production",
        "food and beverage production",
        "food preparation",
        "cookery",
        "pastry and baking",
        "baking technology",
        "catering and accommodation",
    ],

    # ── AGRICULTURE & NATURAL RESOURCES ──────────────────────────────────────
    "Agronomist": [
        # Specific crop/plant sciences — NOT broad "agriculture" (matches extension too)
        "agronomy",
        "crop science",
        "crop production",
        "horticulture",
        "plant science",
        "dry land agriculture",
    ],
    "Agricultural Extension Officer": [
        "agricultural extension",
        "agricultural education and extension",
        "agricultural education & extension",
        "agribusiness",
        "agribusiness management",
        "soil science",
        "irrigation",
        "farm management",
        "agriculture and human ecology",
    ],
    "Food Scientist & Technologist": [
        "food science and technology",
        "food science & technology",
        "food science and management",
        "food technology and quality",
        "dairy technology",
        "dairy science",
        "meat science",
        "food processing technology",
        "food safety",
    ],
    "Livestock & Animal Husbandry Specialist": [
        "animal production",
        "animal science",
        "animal science and management",
        "animal health and production",
        "dairy farm management",
        "poultry management",
        "range management",
        "livestock",
    ],
    "Forestry & Natural Resources Officer": [
        "forestry",
        "agroforestry",
        "bio-resources management",
        "conservation biology",
        "natural resource management",
    ],
    "Fisheries & Aquaculture Officer": [
        # Remove "marine" — matched marine engineering and marine business
        "fisheries",
        "aquaculture",
        "aquatic science",
        "applied aquatic",
        "fisheries and aquatic",
        "oceanography",
    ],

    # ── TECHNICAL (TVET DIPLOMA / CERTIFICATE L5 / KMTC) ─────────────────────
    "Electrician & Electrical Technician": [
        "electrical installation",
        "electrical and electronic engineering",
        "solar energy",
        "renewable energy",
        "electrical technology",
        "power engineering",
    ],
    "Automotive Technician (Mechanic)": [
        "automotive",
        "motor vehicle",
        "motor mechanics",
        "diesel plant",
    ],
    "Building & Construction Technician": [
        "building construction",
        "building technology",
        "civil engineering technology",
        "masonry",
        "carpentry",
        "plumbing",
        "building and civil engineering technology",
    ],
    "Welder & Metal Fabricator": [
        "welding and fabrication",
        "welding & fabrication",
        "marine welding",
        "metal fabrication",
        "sheet metal",
    ],
}


class Command(BaseCommand):
    help = "Add new career profiles and link all courses to the correct careers by keyword"

    def add_arguments(self, parser):
        parser.add_argument(
            "--link-only", action="store_true",
            help="Skip profile creation — only re-run the course linking step"
        )

    def handle(self, *args, **options):
        if not options["link_only"]:
            self._seed_profiles()
        self._link_courses()

    def _seed_profiles(self):
        created = updated = 0
        for data in NEW_CAREERS:
            obj, c = CareerProfile.objects.update_or_create(
                title=data["title"],
                defaults={
                    "icon":               data["icon"],
                    "demand_level":       data["demand_level"],
                    "average_salary":     data["average_salary"],
                    "career_tags":        data["career_tags"],
                    "description":        data["description"],
                    "duties":             data["duties"],
                    "skills_required":    data["skills_required"],
                    "educational_pathway": data["educational_pathway"],
                    "job_opportunities":  data["job_opportunities"],
                    "future_outlook":     data["future_outlook"],
                },
            )
            if c:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Profiles: {created} created, {updated} updated ({created + updated} processed)"
        ))

    def _link_courses(self):
        total_links = 0
        profiles_linked = 0

        for profile_title, keywords in COURSE_KEYWORD_MAP.items():
            # Skip profiles where no keywords were defined (e.g. duplicate entries)
            if not keywords:
                continue

            try:
                profile = CareerProfile.objects.get(title=profile_title)
            except CareerProfile.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  SKIP (not found): {profile_title}"))
                continue

            # Build OR query for all keywords
            q = Q()
            for kw in keywords:
                q |= Q(name__icontains=kw)

            # Only link Degree, TVET Diploma (L6), TVET Certificate (L5), KMTC
            # Exclude teacher training diplomas from non-teaching career profiles
            is_teacher_profile = any(
                kw in profile_title.lower()
                for kw in ("teacher", "early childhood", "special needs")
            )
            qs = Course.objects.filter(q, course_type__name__in=ALLOWED_COURSE_TYPES)
            if not is_teacher_profile:
                qs = qs.exclude(name__icontains="secondary teacher education")
            matched = qs
            count = matched.count()

            if count:
                profile.related_courses.set(matched)
                total_links += count
                profiles_linked += 1
                self.stdout.write(f"  {profile_title}: {count} courses linked")
            else:
                profile.related_courses.clear()
                self.stdout.write(self.style.WARNING(f"  {profile_title}: 0 matches"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone — {total_links} course links across {profiles_linked} profiles."
        ))
