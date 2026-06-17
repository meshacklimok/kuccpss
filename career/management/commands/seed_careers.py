from django.core.management.base import BaseCommand
from career.models import CareerProfile, QuizQuestion, QuizOption


CAREERS = [
    {
        "title": "Software Developer",
        "icon": "fas fa-code",
        "demand_level": "very_high",
        "average_salary": "KSh 80,000 – 350,000/month",
        "career_tags": "technology,engineering",
        "description": (
            "Software developers design, build, and maintain the applications and systems that power "
            "our digital world — from mobile banking apps to hospital management systems."
        ),
        "duties": (
            "• Write, test, and debug code in languages such as Python, JavaScript, Java, or Kotlin\n"
            "• Design software architecture and database schemas\n"
            "• Collaborate with product managers and designers\n"
            "• Review code written by peers and mentor junior developers\n"
            "• Deploy and monitor applications in cloud environments (AWS, GCP, Azure)\n"
            "• Maintain and improve existing systems to ensure reliability and performance"
        ),
        "skills_required": (
            "• Proficiency in at least one programming language (Python, JavaScript, Java)\n"
            "• Problem-solving and logical thinking\n"
            "• Version control with Git\n"
            "• Knowledge of databases (SQL/NoSQL)\n"
            "• Communication and teamwork skills"
        ),
        "educational_pathway": (
            "1. KCSE — Aim for B+ or above, especially in Mathematics and Sciences\n"
            "2. Bachelor of Science in Computer Science / Software Engineering (4 years)\n"
            "   — Available at UoN, KU, JKUAT, Strathmore, Maseno\n"
            "3. Industry certifications: AWS, Google Cloud, Meta Developer\n"
            "4. Build a portfolio of 3–5 real projects on GitHub\n"
            "5. Internship or attachment during 3rd year\n"
            "6. Entry-level roles: Junior Developer → Mid-level → Senior → Tech Lead"
        ),
        "job_opportunities": (
            "• Fintech companies (M-Pesa, Equity Bank, KCB, Safaricom)\n"
            "• Tech startups in Silicon Savannah (Nairobi)\n"
            "• Global companies via remote work (Google, Microsoft, Amazon)\n"
            "• Government agencies (eCitizen, NTSA, IEBC)\n"
            "• NGOs and development organisations (USAID, UNICEF)\n"
            "• Freelance & consultancy work"
        ),
        "future_outlook": (
            "Kenya's tech sector is booming. Nairobi's Silicon Savannah is Africa's leading startup hub, "
            "and demand for software developers is growing 30% annually. Remote work has opened global "
            "opportunities with USD-denominated salaries. AI and cloud skills will be critical by 2030."
        ),
    },
    {
        "title": "Data Scientist",
        "icon": "fas fa-brain",
        "demand_level": "very_high",
        "average_salary": "KSh 120,000 – 450,000/month",
        "career_tags": "technology,science",
        "description": (
            "Data scientists extract insights from large datasets to drive business decisions, using "
            "statistics, machine learning, and programming to turn raw data into actionable intelligence."
        ),
        "duties": (
            "• Collect, clean, and process large datasets from multiple sources\n"
            "• Build machine learning and AI models for prediction and classification\n"
            "• Create data visualisations and dashboards for stakeholders\n"
            "• Collaborate with engineering teams to deploy ML models\n"
            "• Write reports and present findings to non-technical executives\n"
            "• Stay current with AI/ML research and best practices"
        ),
        "skills_required": (
            "• Python or R programming\n"
            "• Statistics and probability\n"
            "• Machine learning frameworks (TensorFlow, scikit-learn, PyTorch)\n"
            "• SQL and big data tools (Spark, BigQuery)\n"
            "• Data visualisation (Tableau, Power BI, Matplotlib)"
        ),
        "educational_pathway": (
            "1. KCSE — Mathematics and Sciences are essential\n"
            "2. BSc Statistics / Mathematics / Computer Science / Data Science (4 years)\n"
            "   — JKUAT, UoN, Strathmore offer relevant programmes\n"
            "3. MSc Data Science (optional but competitive advantage)\n"
            "4. Online certifications: Google Data Analytics, Coursera ML Specialisation\n"
            "5. Kaggle competitions to build public portfolio\n"
            "6. Internship at a bank, telco, or research org"
        ),
        "job_opportunities": (
            "• Commercial banks (Equity, KCB, Cooperative Bank)\n"
            "• Telecommunications (Safaricom, Airtel)\n"
            "• Government statistical agencies (KNBS, KRA)\n"
            "• International NGOs and research institutions\n"
            "• E-commerce platforms (Jumia, Glovo)\n"
            "• Global remote roles with USD salaries"
        ),
        "future_outlook": (
            "AI and data science are the fastest-growing fields globally. In Kenya, banks, telcos, and "
            "government agencies are investing heavily in data infrastructure. Professionals with "
            "Python + ML skills command the highest salaries in the tech sector."
        ),
    },
    {
        "title": "Cybersecurity Analyst",
        "icon": "fas fa-shield-alt",
        "demand_level": "very_high",
        "average_salary": "KSh 100,000 – 400,000/month",
        "career_tags": "technology",
        "description": (
            "Cybersecurity analysts protect organisations' digital assets from hackers, data breaches, "
            "and cyber threats — a critical role as Kenya's digital economy grows rapidly."
        ),
        "duties": (
            "• Monitor networks and systems for security breaches and intrusions\n"
            "• Conduct vulnerability assessments and penetration tests\n"
            "• Respond to security incidents and coordinate recovery\n"
            "• Develop and enforce security policies\n"
            "• Train staff on cybersecurity awareness\n"
            "• Research emerging threats and recommend countermeasures"
        ),
        "skills_required": (
            "• Network fundamentals (TCP/IP, firewalls, VPNs)\n"
            "• Security tools: Wireshark, Metasploit, Nmap, SIEM\n"
            "• Programming knowledge (Python, Bash scripting)\n"
            "• Risk assessment and threat modelling\n"
            "• Incident response and digital forensics"
        ),
        "educational_pathway": (
            "1. KCSE — Mathematics and Physics are important\n"
            "2. BSc Information Technology / Computer Science / Cybersecurity (4 years)\n"
            "3. Professional certifications: CEH, CompTIA Security+, CISSP, OSCP\n"
            "4. Practice on platforms: TryHackMe, HackTheBox, PicoCTF\n"
            "5. Entry roles: Security Analyst → Senior Analyst → CISO"
        ),
        "job_opportunities": (
            "• Banks and financial institutions\n"
            "• Government agencies (KRA, NTSA, Communications Authority)\n"
            "• Telecommunications companies\n"
            "• Cybersecurity firms and consulting companies\n"
            "• International organisations and embassies\n"
            "• Remote security roles for global firms"
        ),
        "future_outlook": (
            "Cybercrime is growing globally and Kenya is no exception. The Communications Authority "
            "has mandated cybersecurity standards for all critical infrastructure. Demand for qualified "
            "security professionals far exceeds supply — making this one of the most lucrative and "
            "future-proof career paths in Kenya's tech sector."
        ),
    },
    {
        "title": "Network Engineer",
        "icon": "fas fa-network-wired",
        "demand_level": "high",
        "average_salary": "KSh 70,000 – 250,000/month",
        "career_tags": "technology,engineering",
        "description": (
            "Network engineers design, implement, and maintain the communication networks that connect "
            "people and organisations — from enterprise LAN networks to national fibre infrastructure."
        ),
        "duties": (
            "• Design and implement LAN, WAN, and wireless network infrastructure\n"
            "• Configure routers, switches, firewalls, and access points\n"
            "• Monitor network performance and troubleshoot connectivity issues\n"
            "• Plan network capacity and upgrades\n"
            "• Maintain documentation of network topology\n"
            "• Support voice over IP (VoIP) and video conferencing systems"
        ),
        "skills_required": (
            "• Networking protocols (TCP/IP, BGP, OSPF, VLANs)\n"
            "• Cisco, Juniper, or Huawei hardware configuration\n"
            "• Network security fundamentals\n"
            "• Linux and Windows Server administration\n"
            "• Problem-solving under pressure"
        ),
        "educational_pathway": (
            "1. KCSE — Mathematics and Physics essential\n"
            "2. BSc Telecommunications / Computer Science / IT (4 years)\n"
            "3. Certifications: CCNA, CCNP, CompTIA Network+\n"
            "4. Entry roles: Network Support Technician → Network Administrator → Network Engineer"
        ),
        "job_opportunities": (
            "• Internet Service Providers (Safaricom, Telkom, Airtel, Faiba)\n"
            "• Banks and financial institutions\n"
            "• Government ICT departments\n"
            "• Large corporations with multi-site networks\n"
            "• ISPs and data centres\n"
            "• Telecommunications consulting firms"
        ),
        "future_outlook": (
            "Kenya's broadband expansion and the roll-out of 5G networks will require thousands of "
            "network engineers over the next decade. Cloud networking and SD-WAN skills are becoming "
            "increasingly critical as organisations move to hybrid cloud infrastructure."
        ),
    },
    {
        "title": "Medical Doctor (Physician)",
        "icon": "fas fa-user-md",
        "demand_level": "very_high",
        "average_salary": "KSh 150,000 – 600,000/month",
        "career_tags": "health,science",
        "description": (
            "Medical doctors diagnose and treat illnesses, prescribe medication, and guide patients "
            "through preventive care — one of the most respected and impactful careers in Kenya."
        ),
        "duties": (
            "• Examine patients and take detailed medical histories\n"
            "• Diagnose diseases and order diagnostic tests\n"
            "• Prescribe and administer treatments and medications\n"
            "• Perform minor surgical procedures\n"
            "• Refer complex cases to specialists\n"
            "• Document patient records and maintain confidentiality\n"
            "• Educate patients and communities on disease prevention"
        ),
        "skills_required": (
            "• Deep knowledge of human anatomy, physiology, and pharmacology\n"
            "• Clinical examination and diagnostic skills\n"
            "• Empathy and excellent communication\n"
            "• Decision-making under pressure\n"
            "• Attention to detail and analytical thinking"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum B+ (mean grade); Biology, Chemistry essential\n"
            "2. MBChB (Bachelor of Medicine and Bachelor of Surgery) — 6 years\n"
            "   — University of Nairobi, Moi University, Egerton, KU, Mt Kenya University\n"
            "3. 1-year internship (mandatory, government hospitals)\n"
            "4. 2-year community service (mandatory)\n"
            "5. Optional: Postgraduate specialisation (3–5 years) — Surgery, Paediatrics, etc.\n"
            "6. Registration with Kenya Medical Practitioners Board (KMPDB)"
        ),
        "job_opportunities": (
            "• Government hospitals (KNH, Moi Teaching, county hospitals)\n"
            "• Private hospitals (Aga Khan, Nairobi Hospital, MP Shah, Avenue)\n"
            "• NGO health programmes (MSF, AMREF, Red Cross)\n"
            "• International organisations (WHO, UNICEF)\n"
            "• Private clinical practice\n"
            "• Medical research institutions"
        ),
        "future_outlook": (
            "Kenya faces a severe doctor shortage — 1 doctor per 10,000 people versus the WHO "
            "recommended 1 per 1,000. Universal Health Coverage (UHC) implementation is creating "
            "unprecedented demand. Specialist doctors in surgery, oncology, and cardiology are "
            "especially needed."
        ),
    },
    {
        "title": "Clinical Officer",
        "icon": "fas fa-stethoscope",
        "demand_level": "very_high",
        "average_salary": "KSh 60,000 – 180,000/month",
        "career_tags": "health",
        "description": (
            "Clinical officers provide primary healthcare services, diagnose common illnesses, and "
            "manage outpatient care — they are the backbone of Kenya's healthcare system."
        ),
        "duties": (
            "• Conduct patient consultations and physical examinations\n"
            "• Diagnose and treat common diseases (malaria, TB, diabetes, hypertension)\n"
            "• Prescribe medications and manage treatment plans\n"
            "• Conduct minor surgical procedures\n"
            "• Refer complex cases to doctors or specialists\n"
            "• Provide maternal and child health services\n"
            "• Maintain accurate patient records"
        ),
        "skills_required": (
            "• Clinical examination and diagnostic skills\n"
            "• Knowledge of pharmacology and treatment protocols\n"
            "• Emergency response and patient management\n"
            "• Communication and patient counselling\n"
            "• Teamwork in clinical settings"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum C+ (mean grade); Biology and Chemistry essential\n"
            "2. Diploma in Clinical Medicine & Surgery (3 years) at KMTC\n"
            "3. Or Upgrade to Bachelor of Science in Clinical Medicine (2 more years)\n"
            "4. Registration with Clinical Officers Council of Kenya (COC-K)\n"
            "5. Specialisation options: Anaesthesia, Orthopaedics, Ophthalmology"
        ),
        "job_opportunities": (
            "• Ministry of Health hospitals and dispensaries\n"
            "• County health facilities across Kenya\n"
            "• KMTC campuses as clinical instructors\n"
            "• NGO health programmes in underserved areas\n"
            "• Private clinics and health centres\n"
            "• Military and National Police health services"
        ),
        "future_outlook": (
            "Clinical officers fill a critical gap in Kenya's healthcare system. With over 88 KMTC "
            "campuses producing graduates, there is growing demand especially in rural and underserved "
            "areas under UHC. Specialised COs in anaesthesia command significantly higher pay."
        ),
    },
    {
        "title": "Registered Nurse",
        "icon": "fas fa-heartbeat",
        "demand_level": "very_high",
        "average_salary": "KSh 45,000 – 150,000/month",
        "career_tags": "health",
        "description": (
            "Nurses provide compassionate direct patient care, administer treatments, monitor health, "
            "and are the largest professional group in Kenya's health workforce."
        ),
        "duties": (
            "• Administer medications and monitor vital signs\n"
            "• Provide wound care, IV therapy, and bedside care\n"
            "• Collaborate with doctors on treatment plans\n"
            "• Educate patients and families on health management\n"
            "• Maintain accurate nursing records\n"
            "• Support patients during surgeries and procedures\n"
            "• Respond to medical emergencies on the ward"
        ),
        "skills_required": (
            "• Clinical nursing skills and patient assessment\n"
            "• Compassion and emotional resilience\n"
            "• Communication with patients and multidisciplinary teams\n"
            "• Critical thinking in emergencies\n"
            "• Infection control and patient safety protocols"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum C+ (mean grade); Biology and Chemistry are key\n"
            "2. Option A: Kenya Registered Community Health Nursing (KRCHN) — 3 years at KMTC\n"
            "3. Option B: BSc Nursing — 4 years (Moi, UoN, JKUAT, KU)\n"
            "4. Option C: Kenya Enrolled Nurse (KEN) — 2 years at KMTC (entry with C-)\n"
            "5. Registration with Nursing Council of Kenya (NCK)\n"
            "6. Specialisation: ICU, Midwifery, Paediatric Nursing, Oncology"
        ),
        "job_opportunities": (
            "• Government and county hospitals\n"
            "• Private hospitals and nursing homes\n"
            "• Community health programmes\n"
            "• International health missions (MSF, Red Cross)\n"
            "• Diaspora nursing in UK, USA, UAE, Canada (highly sought after)\n"
            "• School and corporate occupational health"
        ),
        "future_outlook": (
            "Kenya has a critical nursing shortage, and international demand is equally high. "
            "Thousands of Kenyan nurses work abroad (UK NHS, US hospitals) earning significantly "
            "higher salaries. Specialised nurses in ICU, theatre, and midwifery earn the most."
        ),
    },
    {
        "title": "Pharmacist",
        "icon": "fas fa-pills",
        "demand_level": "high",
        "average_salary": "KSh 80,000 – 250,000/month",
        "career_tags": "health,science",
        "description": (
            "Pharmacists ensure safe medication use by dispensing prescriptions, counselling patients, "
            "and advising healthcare teams on drug therapy — a science-heavy, patient-facing role."
        ),
        "duties": (
            "• Dispense prescription medications accurately\n"
            "• Counsel patients on correct dosage, side effects, and interactions\n"
            "• Review prescriptions for errors or contraindications\n"
            "• Manage pharmaceutical inventory and cold chain\n"
            "• Collaborate with doctors on complex medication regimens\n"
            "• Compound specialised medications as needed\n"
            "• Ensure compliance with pharmaceutical regulations"
        ),
        "skills_required": (
            "• Deep knowledge of pharmacology and therapeutics\n"
            "• Attention to detail (medication errors can be fatal)\n"
            "• Patient communication and counselling\n"
            "• Chemistry knowledge\n"
            "• Inventory management and business skills (for pharmacy owners)"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum B (mean grade); Chemistry, Biology, Mathematics essential\n"
            "2. Bachelor of Pharmacy (BPharm) — 5 years (UoN, MTRH, Strathmore SMPC)\n"
            "3. 1-year internship in a registered pharmacy or hospital\n"
            "4. Registration with Pharmacy and Poisons Board Kenya\n"
            "5. Optional: Masters in Clinical Pharmacy or Pharmaceutical Sciences"
        ),
        "job_opportunities": (
            "• Hospital pharmacies (KNH, Aga Khan, private hospitals)\n"
            "• Community pharmacies (Chain pharmacies: Goodlife, Haltons, Medivet)\n"
            "• Pharmaceutical manufacturing companies\n"
            "• KEMSA and drug regulatory authorities\n"
            "• NGO health supply chain programmes\n"
            "• Academic and research institutions"
        ),
        "future_outlook": (
            "The pharmaceutical sector in Kenya is growing with local manufacturing expanding "
            "and UHC driving increased medicine access. Community pharmacy ownership is highly "
            "lucrative for entrepreneurial pharmacists. Global demand, especially in the Gulf states, "
            "also offers excellent opportunities."
        ),
    },
    {
        "title": "Civil Engineer",
        "icon": "fas fa-hard-hat",
        "demand_level": "high",
        "average_salary": "KSh 90,000 – 350,000/month",
        "career_tags": "engineering,construction",
        "description": (
            "Civil engineers plan, design, and supervise the construction of Kenya's infrastructure — "
            "roads, bridges, dams, buildings, and water systems that drive national development."
        ),
        "duties": (
            "• Design and draft engineering plans for structures and infrastructure\n"
            "• Conduct site surveys and soil/material testing\n"
            "• Supervise construction projects and manage contractors\n"
            "• Ensure structures meet safety and environmental standards\n"
            "• Prepare cost estimates and project schedules\n"
            "• Conduct structural inspections and quality control\n"
            "• Liaise with government, clients, and project stakeholders"
        ),
        "skills_required": (
            "• Mathematics, physics, and structural analysis\n"
            "• AutoCAD and civil engineering design software\n"
            "• Project management and leadership\n"
            "• Knowledge of building codes and regulations\n"
            "• Problem-solving and decision-making"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum B+ (mean grade); Mathematics and Physics are critical\n"
            "2. BSc Civil Engineering — 5 years (UoN, JKUAT, TU-K, Dedan Kimathi)\n"
            "3. Graduate Engineer attachment/internship\n"
            "4. Graduate membership: Engineers Board of Kenya (EBK)\n"
            "5. Professional Engineer (PE) registration after 3 years experience\n"
            "6. Optional: MSc Structural / Geotechnical / Water Resources Engineering"
        ),
        "job_opportunities": (
            "• Ministry of Public Works and Housing\n"
            "• Kenya National Highways Authority (KeNHA)\n"
            "• Construction companies and real estate developers\n"
            "• Consulting engineering firms (Arup, Knight Frank, Mott MacDonald Kenya)\n"
            "• County governments for infrastructure projects\n"
            "• NGOs and development banks (World Bank, AfDB projects)"
        ),
        "future_outlook": (
            "Kenya's infrastructure boom — Vision 2030 projects, affordable housing programme, "
            "and SGR expansion — means sustained high demand for civil engineers. "
            "Specialising in structural or transport engineering and getting registered PE status "
            "significantly boosts earning potential."
        ),
    },
    {
        "title": "Electrical Engineer",
        "icon": "fas fa-bolt",
        "demand_level": "high",
        "average_salary": "KSh 80,000 – 300,000/month",
        "career_tags": "engineering",
        "description": (
            "Electrical engineers design and maintain electrical systems — from power generation and "
            "distribution networks to electronic control systems and renewable energy installations."
        ),
        "duties": (
            "• Design electrical systems for buildings, factories, and power plants\n"
            "• Install and maintain transformers, switchgear, and distribution panels\n"
            "• Work on solar PV, wind, and hydro renewable energy projects\n"
            "• Troubleshoot electrical faults and power quality issues\n"
            "• Ensure compliance with electrical safety regulations\n"
            "• Supervise electrical contractors and technicians"
        ),
        "skills_required": (
            "• Circuit design and power systems analysis\n"
            "• AutoCAD Electrical and ETAP software\n"
            "• Knowledge of Kenya Power grid standards\n"
            "• Renewable energy systems (solar, wind)\n"
            "• Safety standards and electrical codes"
        ),
        "educational_pathway": (
            "1. KCSE — Mathematics and Physics are essential\n"
            "2. BSc Electrical Engineering / Electrical & Electronics Engineering — 5 years\n"
            "   (JKUAT, UoN, TU-K, Dedan Kimathi University)\n"
            "3. Graduate engineer registration with Engineers Board of Kenya (EBK)\n"
            "4. Renewable energy certifications: SEAI, IRENA training\n"
            "5. Professional Engineer registration after 3 years"
        ),
        "job_opportunities": (
            "• Kenya Power & Lighting Company (KPLC)\n"
            "• Kenya Electricity Generating Company (KenGen)\n"
            "• Rural Electrification Authority\n"
            "• Solar energy companies (Solar Africa, Azuri Technologies)\n"
            "• Construction and real estate firms\n"
            "• Manufacturing plants and industrial facilities"
        ),
        "future_outlook": (
            "Kenya's renewable energy target (100% clean energy by 2030) and the Last Mile Connectivity "
            "project are creating massive demand for electrical engineers. Solar energy is booming "
            "with off-grid electrification projects expanding across rural Kenya."
        ),
    },
    {
        "title": "Accountant (CPA)",
        "icon": "fas fa-calculator",
        "demand_level": "high",
        "average_salary": "KSh 60,000 – 250,000/month",
        "career_tags": "finance,business",
        "description": (
            "Accountants manage financial records, prepare reports, ensure tax compliance, and help "
            "organisations make sound financial decisions — a core role in every business."
        ),
        "duties": (
            "• Prepare financial statements (income statement, balance sheet, cash flow)\n"
            "• Manage accounts payable and receivable\n"
            "• Conduct internal and external audits\n"
            "• Prepare and file tax returns (PAYE, VAT, Corporate Tax)\n"
            "• Advise management on cost control and financial planning\n"
            "• Maintain compliance with IFRS and Kenya Revenue Authority rules\n"
            "• Prepare payroll and benefits administration"
        ),
        "skills_required": (
            "• Financial reporting and analysis\n"
            "• Accounting software (QuickBooks, Sage, SAP, Xero)\n"
            "• Tax legislation knowledge (Kenya Revenue Authority)\n"
            "• Attention to detail and integrity\n"
            "• Communication and presentation skills"
        ),
        "educational_pathway": (
            "1. KCSE — Mathematics B+ recommended; Commerce subjects helpful\n"
            "2. Option A: BCom / BSc Accounting (4 years) — KU, USIU, Strathmore, UoN\n"
            "3. Option B: CPA Kenya (Certified Public Accountant) — KASNEB exams (3 levels)\n"
            "4. ICPAK membership after completing CPA-K\n"
            "5. Optional: ACCA, CIMA for international credibility\n"
            "6. MBA for senior management roles"
        ),
        "job_opportunities": (
            "• Audit firms (Deloitte, KPMG, PWC, EY — 'Big Four' in Nairobi)\n"
            "• Banks and financial institutions\n"
            "• Manufacturing and retail companies\n"
            "• Government ministries and parastatals\n"
            "• NGOs and development organisations\n"
            "• Entrepreneurial: Start your own CPA practice"
        ),
        "future_outlook": (
            "Every organisation needs accountants. ICPAK membership significantly raises earning "
            "potential. Big Four audit firms are the gateway to top careers. Kenya's growing SME "
            "sector creates huge demand for affordable accounting services — entrepreneurial CPAs "
            "can build thriving practices."
        ),
    },
    {
        "title": "Advocate / Lawyer",
        "icon": "fas fa-balance-scale",
        "demand_level": "high",
        "average_salary": "KSh 80,000 – 500,000/month",
        "career_tags": "law,governance",
        "description": (
            "Advocates advise clients on legal matters, draft contracts and legal documents, "
            "and represent clients in courts — a prestigious career at the heart of justice."
        ),
        "duties": (
            "• Advise clients on their legal rights and obligations\n"
            "• Draft contracts, wills, and legal agreements\n"
            "• Represent clients in civil and criminal court proceedings\n"
            "• Conduct legal research and build case arguments\n"
            "• Negotiate settlements and mediate disputes\n"
            "• Ensure compliance with Kenyan statutes and regulations\n"
            "• Protect client confidentiality at all times"
        ),
        "skills_required": (
            "• Deep knowledge of Kenyan law (Constitutional, Commercial, Criminal, Family)\n"
            "• Analytical reasoning and research skills\n"
            "• Oral and written advocacy\n"
            "• Negotiation and persuasion\n"
            "• Time management across multiple cases"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum B+ (mean grade); Languages and Arts subjects beneficial\n"
            "2. LLB (Bachelor of Laws) — 4 years (UoN, KU, Strathmore, USIU, Kabarak)\n"
            "3. Kenya School of Law (KSL) — 1-year Advocates Training Programme (ATP)\n"
            "4. Bar Examination and admission to the Roll of Advocates\n"
            "5. Pupillage at a law firm (6 months)\n"
            "6. Optional: LLM for specialisation (Commercial Law, International Law, IP)"
        ),
        "job_opportunities": (
            "• Private law firms (Oraro, Anjarwalla, Kaplan & Stratton)\n"
            "• Corporate legal departments (banks, multinationals)\n"
            "• State Law Office (Attorney General's office)\n"
            "• DPP and prosecution services\n"
            "• NGOs and human rights organisations\n"
            "• Judiciary (Magistrate → Judge pathway)"
        ),
        "future_outlook": (
            "Kenya's growing economy and complex regulatory environment create strong demand for "
            "commercial lawyers. Specialisation in fintech, land law, or environmental law is highly "
            "lucrative. Senior partners at top firms earn millions monthly."
        ),
    },
    {
        "title": "Secondary School Teacher",
        "icon": "fas fa-chalkboard-teacher",
        "demand_level": "high",
        "average_salary": "KSh 30,000 – 120,000/month",
        "career_tags": "education",
        "description": (
            "Secondary school teachers shape the next generation by teaching KCSE subjects, "
            "mentoring students, and preparing them for higher education and life."
        ),
        "duties": (
            "• Prepare and deliver lessons aligned to the Kenya Curriculum (KICD)\n"
            "• Evaluate student progress through assignments, tests, and exams\n"
            "• Provide individualised support to struggling learners\n"
            "• Prepare students for KCSE national examinations\n"
            "• Maintain student records and communicate with parents\n"
            "• Participate in school co-curricular activities and administration\n"
            "• Continuously update subject knowledge and teaching methodology"
        ),
        "skills_required": (
            "• Deep subject knowledge in teaching specialisation\n"
            "• Lesson planning and curriculum delivery\n"
            "• Classroom management and student motivation\n"
            "• Assessment and feedback skills\n"
            "• Patience, empathy, and communication"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum C+ (mean grade); Strong grades in chosen subjects\n"
            "2. Bachelor of Education (BEd) — 4 years, choose 2 teaching subjects\n"
            "   — KU, Moi, Egerton, UoN, TU-K, Maseno, many private universities\n"
            "3. Teacher Service Commission (TSC) registration and certification\n"
            "4. Optional: MEd for HOD, Deputy Principal, or Principal roles\n"
            "5. International teaching options: UK, Middle East with international schools"
        ),
        "job_opportunities": (
            "• TSC-employed public secondary schools (47 counties)\n"
            "• Private secondary schools and international schools\n"
            "• National schools (Starehe, Alliance, Mang'u, Limuru)\n"
            "• International schools in Nairobi (IB, IGCSE curriculum)\n"
            "• Online tutoring platforms\n"
            "• Teacher training colleges"
        ),
        "future_outlook": (
            "CBC implementation is creating demand for retrained and newly-qualified teachers. "
            "International schools in Kenya pay significantly more than TSC scales. "
            "Diaspora teaching in the UK, Middle East, and East Asia is a growing trend "
            "for Kenyan teachers seeking higher income."
        ),
    },
    {
        "title": "Economist",
        "icon": "fas fa-chart-line",
        "demand_level": "high",
        "average_salary": "KSh 80,000 – 350,000/month",
        "career_tags": "finance,business,governance",
        "description": (
            "Economists analyse economic data, model policy impacts, forecast trends, and advise "
            "governments, corporations, and international organisations on financial and social policy."
        ),
        "duties": (
            "• Analyse economic indicators: inflation, GDP, employment, trade balance\n"
            "• Build econometric models to forecast economic trends\n"
            "• Assess the impact of government policies\n"
            "• Prepare economic research reports and policy briefs\n"
            "• Advise on pricing, investment, and resource allocation decisions\n"
            "• Monitor global economic developments and their local impact"
        ),
        "skills_required": (
            "• Statistical analysis and econometrics (STATA, R, Python)\n"
            "• Economic theory (micro and macro)\n"
            "• Research and report writing\n"
            "• Data visualisation and presentation\n"
            "• Critical thinking and policy analysis"
        ),
        "educational_pathway": (
            "1. KCSE — Strong Mathematics is essential\n"
            "2. BSc Economics or BA Economics — 4 years (UoN, KU, Strathmore, USIU, Moi)\n"
            "3. MSc Economics or MBA for senior roles\n"
            "4. Professional certifications: CFA (Chartered Financial Analyst)\n"
            "5. PhD for research or university positions"
        ),
        "job_opportunities": (
            "• Central Bank of Kenya (CBK)\n"
            "• Kenya Revenue Authority (KRA)\n"
            "• World Bank, IMF, UN Economic Commission for Africa\n"
            "• Commercial banks and investment firms\n"
            "• Research institutions (KIPPRA, IPAR)\n"
            "• Consulting firms (McKinsey, Deloitte, KPMG)"
        ),
        "future_outlook": (
            "Kenya's integration into regional and global markets, combined with complex policy "
            "challenges (debt management, inflation, poverty reduction), creates strong demand for "
            "well-trained economists. International organisations pay extremely competitive salaries."
        ),
    },
    {
        "title": "Agronomist",
        "icon": "fas fa-leaf",
        "demand_level": "high",
        "average_salary": "KSh 50,000 – 200,000/month",
        "career_tags": "agriculture,science",
        "description": (
            "Agronomists apply science to improve crop production — advising farmers on seeds, "
            "soil, fertilisers, and pest management to boost yields and food security in Kenya."
        ),
        "duties": (
            "• Conduct soil testing and analysis\n"
            "• Advise farmers on crop selection and rotation for their land\n"
            "• Recommend fertiliser and irrigation programmes\n"
            "• Diagnose and treat crop pests and diseases\n"
            "• Conduct field trials on new seed varieties\n"
            "• Train smallholder farmers on modern farming methods\n"
            "• Work with agri-input companies to introduce new products"
        ),
        "skills_required": (
            "• Soil science and plant biology\n"
            "• Crop protection (IPM, pesticide management)\n"
            "• GIS and precision agriculture tools\n"
            "• Communication and farmer training skills\n"
            "• Business acumen for agribusiness roles"
        ),
        "educational_pathway": (
            "1. KCSE — Biology, Chemistry, Agriculture subjects are important\n"
            "2. BSc Agronomy / Agriculture / Crop Science — 4 years (Egerton, UoN, JKUAT)\n"
            "3. Higher Diploma in Agriculture (for extension officer roles)\n"
            "4. Optional: MSc Agronomy or Plant Pathology\n"
            "5. Membership: Agrochemicals Association of Kenya"
        ),
        "job_opportunities": (
            "• Ministry of Agriculture extension services\n"
            "• County agriculture departments\n"
            "• Agri-input companies (Yara, Syngenta, MEA Fertilizers)\n"
            "• Large-scale farms (flower farms, tea estates, horticulture)\n"
            "• NGOs and international development organisations\n"
            "• Agribusiness startups and cooperatives"
        ),
        "future_outlook": (
            "Climate change is making agronomy knowledge more critical for Kenya's farming sector. "
            "Precision agriculture and digital farming are the future. With 70% of Kenyans depending "
            "on agriculture, the sector needs urgently modernised expertise."
        ),
    },
    {
        "title": "Environmental Scientist",
        "icon": "fas fa-globe",
        "demand_level": "high",
        "average_salary": "KSh 60,000 – 200,000/month",
        "career_tags": "environment,science",
        "description": (
            "Environmental scientists study ecosystems, assess pollution, and advise on sustainability "
            "to protect Kenya's natural resources while enabling responsible economic development."
        ),
        "duties": (
            "• Conduct Environmental Impact Assessments (EIAs) for development projects\n"
            "• Monitor water, soil, and air quality\n"
            "• Advise on waste management and pollution control\n"
            "• Support climate change adaptation and mitigation plans\n"
            "• Work with NEMA on environmental compliance\n"
            "• Research biodiversity and ecosystem health"
        ),
        "skills_required": (
            "• Environmental chemistry and ecology\n"
            "• GIS and remote sensing tools\n"
            "• Environmental law and NEMA regulations\n"
            "• Research and scientific writing\n"
            "• Stakeholder engagement"
        ),
        "educational_pathway": (
            "1. KCSE — Biology, Chemistry, Geography helpful\n"
            "2. BSc Environmental Science / Natural Resources / Ecology — 4 years\n"
            "   (Moi, UoN, JKUAT, Kenyatta, Egerton)\n"
            "3. Lead Expert registration with NEMA for EIA practice\n"
            "4. MSc Environmental Management or Climate Change\n"
            "5. Professional membership: Environmental Institute of Kenya (EIK)"
        ),
        "job_opportunities": (
            "• National Environment Management Authority (NEMA)\n"
            "• Kenya Forest Service and Kenya Wildlife Service\n"
            "• Environmental consultancy firms\n"
            "• Mining and oil companies (environmental compliance)\n"
            "• NGOs (WWF Kenya, Nature Kenya, GreenBelt Movement)\n"
            "• International organisations (UNEP headquarters in Nairobi)"
        ),
        "future_outlook": (
            "Nairobi hosts UNEP headquarters — giving Kenya a unique position in global "
            "environmental governance. EIA requirements for all major projects drive strong demand "
            "for environmental consultants. Climate change careers will explode globally in the next decade."
        ),
    },
    {
        "title": "Journalist & Media Personality",
        "icon": "fas fa-microphone",
        "demand_level": "medium",
        "average_salary": "KSh 40,000 – 300,000/month",
        "career_tags": "creative,media",
        "description": (
            "Journalists investigate and report stories that inform and hold power to account — "
            "from TV anchors to investigative reporters, digital content creators, and podcast hosts."
        ),
        "duties": (
            "• Research, investigate, and verify news stories\n"
            "• Conduct interviews and gather information from sources\n"
            "• Write, edit, and present news articles or broadcasts\n"
            "• Create multimedia content (video, podcast, social media)\n"
            "• Build and maintain a network of contacts and sources\n"
            "• Adhere to journalistic ethics and editorial standards"
        ),
        "skills_required": (
            "• Strong writing and storytelling skills\n"
            "• Research and investigative ability\n"
            "• Broadcast presentation (for TV/radio)\n"
            "• Video production and editing\n"
            "• Social media and digital journalism skills"
        ),
        "educational_pathway": (
            "1. KCSE — Languages (English, Kiswahili) are key; minimum C+\n"
            "2. BA Mass Communication / Journalism — 4 years (UoN, USIU, Daystar, Moi)\n"
            "3. Or Diploma in Journalism (2–3 years at KIB, KIMC)\n"
            "4. Internship at a media house (Nation, Standard, KBC, NTV, Citizen)\n"
            "5. Build portfolio: articles, videos, podcast episodes"
        ),
        "job_opportunities": (
            "• Nation Media Group, Standard Group, Royal Media Services\n"
            "• KBC and county radio stations\n"
            "• Digital media startups\n"
            "• International media (BBC Africa, CNN, Al Jazeera Kenya)\n"
            "• Corporate communications and PR departments\n"
            "• Freelance digital content creation (YouTube, podcast, blogs)"
        ),
        "future_outlook": (
            "Digital journalism and content creation are transforming media. YouTubers, podcasters, "
            "and digital journalists can earn far more than traditional media salaries. "
            "Investigative journalism and data journalism are growing fields. "
            "Media personalities with strong social media presence are highly valued."
        ),
    },
    {
        "title": "Graphic Designer & Creative Director",
        "icon": "fas fa-paint-brush",
        "demand_level": "high",
        "average_salary": "KSh 50,000 – 250,000/month",
        "career_tags": "creative,technology",
        "description": (
            "Graphic designers create visual communications — logos, branding, UI designs, marketing "
            "materials, and digital content — that shape how businesses look and feel."
        ),
        "duties": (
            "• Design logos, brand identities, and visual guidelines\n"
            "• Create marketing materials: brochures, banners, social media graphics\n"
            "• Design user interfaces for apps and websites (UI/UX)\n"
            "• Collaborate with marketing teams on campaigns\n"
            "• Prepare files for print and digital production\n"
            "• Pitch creative concepts to clients"
        ),
        "skills_required": (
            "• Adobe Creative Suite (Photoshop, Illustrator, InDesign, XD)\n"
            "• Figma for UI/UX design\n"
            "• Colour theory, typography, layout principles\n"
            "• Client communication and presentation\n"
            "• Portfolio development and self-promotion"
        ),
        "educational_pathway": (
            "1. KCSE — Art, Design, and Mathematics helpful; minimum C\n"
            "2. BSc / BA Graphic Design or Fine Art — 4 years\n"
            "   (Kenyatta, Nairobi, USIU, KCA, Limkokwing Nairobi)\n"
            "3. Diploma in Graphic Design (2–3 years)\n"
            "4. Online certifications: Google UX Design, Adobe Certified Professional\n"
            "5. Build a portfolio on Behance and Dribbble"
        ),
        "job_opportunities": (
            "• Advertising agencies (Ogilvy Nairobi, Saatchi & Saatchi)\n"
            "• Media and publishing houses\n"
            "• Brand and marketing departments of corporations\n"
            "• Tech startups needing UI/UX designers\n"
            "• Freelance and agency work\n"
            "• Digital marketing and social media agencies"
        ),
        "future_outlook": (
            "Digital transformation means every business needs visual design. UI/UX design "
            "is one of the highest-paying creative specialisations. Motion graphics and "
            "3D design skills are increasingly demanded by media and entertainment companies. "
            "Remote freelance work gives Kenyan designers access to global client rates."
        ),
    },
    {
        "title": "Mechanical Engineer",
        "icon": "fas fa-cogs",
        "demand_level": "high",
        "average_salary": "KSh 75,000 – 280,000/month",
        "career_tags": "engineering",
        "description": (
            "Mechanical engineers design, build, and maintain machines, engines, and mechanical "
            "systems — from industrial equipment and vehicles to HVAC systems and manufacturing lines."
        ),
        "duties": (
            "• Design mechanical components and systems using CAD software\n"
            "• Analyse structural and thermal performance of machines\n"
            "• Oversee manufacturing processes and quality control\n"
            "• Maintain and troubleshoot industrial machinery\n"
            "• Manage maintenance schedules and teams\n"
            "• Ensure compliance with engineering and safety standards"
        ),
        "skills_required": (
            "• Solid Works, AutoCAD, ANSYS for design and simulation\n"
            "• Thermodynamics and fluid mechanics\n"
            "• Manufacturing processes and materials science\n"
            "• Project management\n"
            "• Problem-solving and mechanical aptitude"
        ),
        "educational_pathway": (
            "1. KCSE — Mathematics and Physics are essential\n"
            "2. BSc Mechanical Engineering — 5 years (JKUAT, TU-K, UoN, Dedan Kimathi)\n"
            "3. Graduate Engineer registration (Engineers Board of Kenya)\n"
            "4. Specialisation: Automotive, Manufacturing, HVAC, Renewable Energy\n"
            "5. Professional Engineer registration after 3 years practice"
        ),
        "job_opportunities": (
            "• Manufacturing plants (Kenya Breweries, BAT, Bamburi Cement, Coca-Cola)\n"
            "• Automotive industry (vehicle assembly, maintenance)\n"
            "• Government parastatals (KENGEN, KPA)\n"
            "• Construction industry (HVAC, plumbing systems)\n"
            "• Oil and gas sector\n"
            "• Engineering consulting firms"
        ),
        "future_outlook": (
            "Kenya's manufacturing ambitions under Vision 2030, combined with growing automotive "
            "assembly and industrial expansion, will require more mechanical engineers. "
            "Renewable energy maintenance and energy efficiency consulting are fast-growing niches."
        ),
    },
    {
        "title": "Social Worker",
        "icon": "fas fa-hand-holding-heart",
        "demand_level": "medium",
        "average_salary": "KSh 35,000 – 120,000/month",
        "career_tags": "social,health",
        "description": (
            "Social workers support vulnerable individuals, families, and communities — from "
            "child protection and mental health support to humanitarian response and community development."
        ),
        "duties": (
            "• Assess the social, emotional, and economic needs of clients\n"
            "• Connect families with government benefits and community resources\n"
            "• Support children at risk of abuse, neglect, or exploitation\n"
            "• Provide counselling and psychosocial support\n"
            "• Manage case files and write detailed reports\n"
            "• Work with probation services, schools, and healthcare\n"
            "• Advocate for policy changes to protect vulnerable groups"
        ),
        "skills_required": (
            "• Empathy and active listening\n"
            "• Case management and documentation\n"
            "• Knowledge of Kenyan social protection laws and policies\n"
            "• Cultural sensitivity\n"
            "• Resilience and emotional regulation"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum C+ (mean grade); Social studies helpful\n"
            "2. BSW (Bachelor of Social Work) — 4 years (UoN, Kenyatta, KCA, Moi)\n"
            "3. Or Diploma in Social Work (2–3 years)\n"
            "4. Internship/placement in a social welfare organisation\n"
            "5. MSW (Master of Social Work) for senior or specialised roles\n"
            "6. Registration with Kenya Association of Social Workers"
        ),
        "job_opportunities": (
            "• Ministry of Gender, Labour and Social Development\n"
            "• Children's homes and child protection services\n"
            "• International NGOs (UNICEF, Save the Children, Plan International)\n"
            "• Hospitals (medical social workers)\n"
            "• Community-based organisations\n"
            "• UNHCR refugee support programmes"
        ),
        "future_outlook": (
            "Kenya's social challenges — urbanisation, youth unemployment, gender-based violence, "
            "and refugee crises — create consistent demand for trained social workers. "
            "NGO and international development organisation roles offer competitive packages "
            "for experienced professionals."
        ),
    },
    {
        "title": "Architect",
        "icon": "fas fa-drafting-compass",
        "demand_level": "high",
        "average_salary": "KSh 80,000 – 400,000/month",
        "career_tags": "engineering,creative",
        "description": (
            "Architects design functional, safe, and beautiful buildings and spaces — from residential "
            "homes and commercial skyscrapers to hospitals, schools, and public spaces."
        ),
        "duties": (
            "• Consult with clients to understand project briefs and requirements\n"
            "• Create architectural designs, drawings, and 3D models\n"
            "• Prepare tender documents and construction drawings\n"
            "• Oversee construction and ensure designs are built as intended\n"
            "• Ensure compliance with building codes and planning regulations\n"
            "• Coordinate with engineers, quantity surveyors, and contractors"
        ),
        "skills_required": (
            "• AutoCAD, ArchiCAD, Revit, SketchUp for design\n"
            "• 3D rendering software (Lumion, V-Ray)\n"
            "• Knowledge of building materials and construction technology\n"
            "• Creative design thinking and spatial reasoning\n"
            "• Project management and client communication"
        ),
        "educational_pathway": (
            "1. KCSE — Mathematics, Art/Drawing are important\n"
            "2. Bachelor of Architecture (BArch) — 5 years (UoN, TU-K, JKUAT)\n"
            "3. 2-year pupillage under a registered architect\n"
            "4. Registration with the Board of Registration of Architects & Quantity Surveyors (BORAQS)\n"
            "5. Optional: MSc Urban Design or Sustainable Architecture"
        ),
        "job_opportunities": (
            "• Architectural firms (Archcraft, Triad Architects Kenya)\n"
            "• Real estate developers\n"
            "• Government (Ministry of Public Works)\n"
            "• County governments planning departments\n"
            "• International design firms\n"
            "• Own architectural practice"
        ),
        "future_outlook": (
            "Kenya's affordable housing programme and continued real estate development in Nairobi, "
            "Kisumu, and coastal cities are creating sustained demand. Sustainable green architecture "
            "and smart city design are high-growth specialisations."
        ),
    },
    {
        "title": "Banker & Financial Analyst",
        "icon": "fas fa-landmark",
        "demand_level": "high",
        "average_salary": "KSh 70,000 – 400,000/month",
        "career_tags": "finance,business",
        "description": (
            "Bankers and financial analysts manage money, credit, and investments — from retail "
            "banking relationship management to investment research and corporate finance advisory."
        ),
        "duties": (
            "• Evaluate loan applications and assess creditworthiness\n"
            "• Manage client relationships and grow business portfolios\n"
            "• Analyse financial statements and investment opportunities\n"
            "• Prepare financial models and valuation reports\n"
            "• Advise corporate clients on mergers, acquisitions, and IPOs\n"
            "• Monitor market trends and interest rate movements"
        ),
        "skills_required": (
            "• Financial analysis and modelling (Excel, Bloomberg)\n"
            "• Credit analysis and risk assessment\n"
            "• Accounting principles (IFRS)\n"
            "• Sales and relationship management\n"
            "• Analytical thinking and attention to detail"
        ),
        "educational_pathway": (
            "1. KCSE — Strong Mathematics required\n"
            "2. BCom Finance / BSc Finance / BA Economics — 4 years\n"
            "   (Strathmore, USIU, KU, UoN)\n"
            "3. CPA-K or ACCA for accounting pathways\n"
            "4. CFA (Chartered Financial Analyst) for investment roles\n"
            "5. MBA for senior banking and finance management"
        ),
        "job_opportunities": (
            "• Commercial banks (Equity, KCB, Absa, Cooperative, NCBA)\n"
            "• Investment banks and stockbrokers (Nairobi Securities Exchange)\n"
            "• Insurance companies and pension funds\n"
            "• Central Bank of Kenya\n"
            "• Private equity and venture capital firms\n"
            "• Mobile money (M-Pesa, Airtel Money)"
        ),
        "future_outlook": (
            "Kenya's financial sector is one of the most sophisticated in Africa. Fintech is booming "
            "with mobile money and digital banking reshaping finance. Senior bankers and CFA "
            "charterholders command the highest salaries in the private sector."
        ),
    },
    {
        "title": "Human Resource Manager",
        "icon": "fas fa-users",
        "demand_level": "medium",
        "average_salary": "KSh 60,000 – 250,000/month",
        "career_tags": "business",
        "description": (
            "HR managers recruit, develop, and retain an organisation's most valuable asset — "
            "its people. They shape company culture, manage performance, and ensure fair employment."
        ),
        "duties": (
            "• Lead recruitment and selection processes\n"
            "• Develop and implement HR policies and procedures\n"
            "• Manage performance review systems and training programmes\n"
            "• Handle employee relations, grievances, and disciplinary matters\n"
            "• Oversee payroll and benefits administration\n"
            "• Ensure compliance with the Employment Act of Kenya\n"
            "• Build organisational culture and drive employee engagement"
        ),
        "skills_required": (
            "• Knowledge of Kenya Employment Act and labour law\n"
            "• Recruitment and talent management\n"
            "• Conflict resolution and mediation\n"
            "• HRIS systems (SAP HR, BambooHR)\n"
            "• Communication, empathy, and confidentiality"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum C+ (mean grade)\n"
            "2. BA / BSc Human Resource Management — 4 years (multiple universities)\n"
            "3. Or BCom with HR specialisation\n"
            "4. Higher Diploma in Human Resource Management (IHRM)\n"
            "5. IHRM membership (Institute of Human Resource Management Kenya)\n"
            "6. MBA for director-level roles"
        ),
        "job_opportunities": (
            "• All medium and large organisations across sectors\n"
            "• HR consulting firms\n"
            "• NGOs and international development organisations\n"
            "• Government ministries and parastatals\n"
            "• Manufacturing and service industries\n"
            "• Recruitment agencies"
        ),
        "future_outlook": (
            "Every growing organisation needs HR professionals. Tech-enabled HR (AI recruitment, "
            "HR analytics) is reshaping the field. Strategic HR business partners with commercial "
            "acumen command high salaries at multinationals."
        ),
    },
    {
        "title": "Agricultural Engineer",
        "icon": "fas fa-tractor",
        "demand_level": "medium",
        "average_salary": "KSh 55,000 – 200,000/month",
        "career_tags": "engineering,agriculture",
        "description": (
            "Agricultural engineers apply engineering principles to farming — designing irrigation "
            "systems, farm machinery, post-harvest facilities, and food processing infrastructure."
        ),
        "duties": (
            "• Design and install irrigation and drainage systems\n"
            "• Select and maintain farm machinery and equipment\n"
            "• Design post-harvest storage and food processing facilities\n"
            "• Implement precision farming and mechanisation systems\n"
            "• Advise on soil conservation and land management\n"
            "• Conduct agricultural infrastructure feasibility studies"
        ),
        "skills_required": (
            "• Irrigation design and hydrology\n"
            "• Farm mechanisation and equipment maintenance\n"
            "• AutoCAD for facility design\n"
            "• Soil science and agronomy basics\n"
            "• Project management"
        ),
        "educational_pathway": (
            "1. KCSE — Mathematics, Physics, Agriculture subjects\n"
            "2. BSc Agricultural Engineering / Agricultural & Biosystems Engineering — 5 years\n"
            "   (Egerton, JKUAT, UoN)\n"
            "3. Engineers Board of Kenya graduate registration\n"
            "4. Specialisation: Irrigation, Precision Agriculture, Food Processing"
        ),
        "job_opportunities": (
            "• Ministry of Agriculture and Irrigation\n"
            "• Large-scale farms (flower farms, tea estates, irrigation schemes)\n"
            "• FAO and international agricultural development organisations\n"
            "• Agricultural machinery dealers and importers\n"
            "• KENGO (Kenya Non-Governmental Organisations)\n"
            "• Irrigation Board of Kenya"
        ),
        "future_outlook": (
            "Kenya's push to modernise agriculture under the Big Four Agenda and food security "
            "goals are creating demand for engineers who can bridge technology and farming. "
            "Drip irrigation, greenhouse farming, and cold chain infrastructure are growth areas."
        ),
    },
    {
        "title": "Biochemist",
        "icon": "fas fa-flask",
        "demand_level": "medium",
        "average_salary": "KSh 55,000 – 200,000/month",
        "career_tags": "science,health",
        "description": (
            "Biochemists study the chemical processes of living organisms — enabling breakthroughs "
            "in medicine, food science, pharmaceuticals, and biotechnology in Kenya and globally."
        ),
        "duties": (
            "• Conduct laboratory experiments on biological samples\n"
            "• Analyse proteins, DNA, enzymes, and cellular processes\n"
            "• Develop and test pharmaceutical compounds and vaccines\n"
            "• Ensure quality control in food and pharmaceutical manufacturing\n"
            "• Write scientific papers and present research findings\n"
            "• Operate and maintain laboratory equipment"
        ),
        "skills_required": (
            "• Laboratory techniques (PCR, chromatography, spectroscopy, ELISA)\n"
            "• Molecular biology and genetics\n"
            "• Data analysis and scientific writing\n"
            "• Attention to detail and precision\n"
            "• Critical thinking and problem-solving"
        ),
        "educational_pathway": (
            "1. KCSE — Biology, Chemistry essential; Mathematics, Physics important\n"
            "2. BSc Biochemistry — 4 years (UoN, Moi, Kenyatta, JKUAT)\n"
            "3. MSc Biochemistry / Biotechnology for advanced research\n"
            "4. PhD for university academic or senior research roles\n"
            "5. Lab certifications: GLP (Good Laboratory Practice)"
        ),
        "job_opportunities": (
            "• Kenya Medical Research Institute (KEMRI)\n"
            "• Pharmaceutical manufacturing companies\n"
            "• Kenya Bureau of Standards (KEBS)\n"
            "• University research departments\n"
            "• Food and beverage quality labs\n"
            "• International research institutions (ILRI, ICRAF)"
        ),
        "future_outlook": (
            "Biotechnology and genomics are reshaping medicine globally. Kenya's growing "
            "pharmaceutical manufacturing sector needs more local biochemists. Research institutions "
            "like KEMRI and ILRI offer excellent research careers and international collaboration."
        ),
    },
    {
        "title": "Marketing & Sales Professional",
        "icon": "fas fa-bullhorn",
        "demand_level": "high",
        "average_salary": "KSh 40,000 – 300,000/month",
        "career_tags": "business,creative",
        "description": (
            "Marketing and sales professionals drive business growth by understanding customers, "
            "building brands, running campaigns, and converting prospects into loyal buyers."
        ),
        "duties": (
            "• Develop and execute marketing campaigns (digital and traditional)\n"
            "• Conduct market research and competitive analysis\n"
            "• Manage social media accounts and content calendars\n"
            "• Build and manage sales pipelines and client relationships\n"
            "• Analyse campaign performance using data and KPIs\n"
            "• Collaborate with product teams and creative agencies"
        ),
        "skills_required": (
            "• Digital marketing: SEO, Google Ads, Meta Ads, email marketing\n"
            "• Sales techniques and negotiation\n"
            "• Analytical tools: Google Analytics, CRM systems\n"
            "• Content creation and copywriting\n"
            "• Communication and public presentation"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum C+; Languages and Business subjects useful\n"
            "2. BA / BSc Marketing or BCom Marketing — 4 years\n"
            "3. CIM (Chartered Institute of Marketing) professional qualifications\n"
            "4. Google Digital Marketing certifications (free online)\n"
            "5. Build a portfolio: managed campaigns, social media accounts, case studies"
        ),
        "job_opportunities": (
            "• Consumer goods companies (Unilever, Procter & Gamble, Bidco)\n"
            "• Banks and financial services\n"
            "• Media and advertising agencies\n"
            "• Tech startups and e-commerce platforms\n"
            "• NGOs for fundraising and communications roles\n"
            "• Freelance digital marketing consultancy"
        ),
        "future_outlook": (
            "Digital marketing is disrupting traditional advertising. Data-driven marketing "
            "professionals with skills in performance marketing and CRM analytics earn premium "
            "salaries. Entrepreneurial marketers can build successful consultancy businesses."
        ),
    },
    {
        "title": "Public Administrator",
        "icon": "fas fa-city",
        "demand_level": "medium",
        "average_salary": "KSh 50,000 – 200,000/month",
        "career_tags": "governance,law",
        "description": (
            "Public administrators manage government services, implement policy, and coordinate "
            "resources to deliver public goods — from county government to national ministries."
        ),
        "duties": (
            "• Implement government policies and regulations at local or national level\n"
            "• Coordinate public service delivery and community programmes\n"
            "• Manage government resources, budgets, and staff\n"
            "• Liaise between communities and government departments\n"
            "• Maintain public records and prepare administrative reports\n"
            "• Handle public complaints and service requests"
        ),
        "skills_required": (
            "• Public policy analysis and implementation\n"
            "• Leadership and management\n"
            "• Understanding of Kenya's devolution framework\n"
            "• Communication and stakeholder management\n"
            "• Budget and resource management"
        ),
        "educational_pathway": (
            "1. KCSE — Minimum C+ (mean grade)\n"
            "2. BA Public Administration / Political Science — 4 years (UoN, KU, JKUAT, Moi)\n"
            "3. Competitive entry to Kenya School of Government (KSG) training programmes\n"
            "4. County Public Service Board (CPSB) appointment process\n"
            "5. MA Public Administration or MPA for senior roles"
        ),
        "job_opportunities": (
            "• Ministry offices and national government departments\n"
            "• County governments (47 counties)\n"
            "• Kenya School of Government (trainer/facilitator)\n"
            "• Public Service Commission (PSC) appointments\n"
            "• Kenya Defence Forces administrative roles\n"
            "• International governance organisations"
        ),
        "future_outlook": (
            "Devolution continues to create roles at county level across Kenya. Public sector "
            "reform is driving demand for professionally trained administrators. "
            "Entry to the national government through the PSC remains competitive but highly secure."
        ),
    },
]


QUIZ_QUESTIONS = [
    {
        "text": "What kind of activities energise you the most?",
        "category": "interest",
        "order": 1,
        "options": [
            {"text": "Building things with code or machines", "career_tags": "technology,engineering", "order": 1},
            {"text": "Helping sick or vulnerable people get better", "career_tags": "health,social", "order": 2},
            {"text": "Analysing numbers, data, and reports", "career_tags": "finance,business,science", "order": 3},
            {"text": "Creating art, designs, or stories", "career_tags": "creative,media", "order": 4},
        ],
    },
    {
        "text": "Which school subjects did you genuinely enjoy?",
        "category": "interest",
        "order": 2,
        "options": [
            {"text": "Mathematics and Physics", "career_tags": "engineering,technology,finance", "order": 1},
            {"text": "Biology and Chemistry", "career_tags": "health,science,agriculture", "order": 2},
            {"text": "History, CRE, and Social Studies", "career_tags": "law,governance,education,social", "order": 3},
            {"text": "Languages, Literature, and Art", "career_tags": "creative,media,education,law", "order": 4},
        ],
    },
    {
        "text": "What type of work environment do you prefer?",
        "category": "interest",
        "order": 3,
        "options": [
            {"text": "An office or lab where I can concentrate deeply", "career_tags": "technology,finance,science", "order": 1},
            {"text": "Outdoors or in the field working with people", "career_tags": "agriculture,environment,social", "order": 2},
            {"text": "A hospital, clinic, or community setting", "career_tags": "health,social", "order": 3},
            {"text": "A creative studio or flexible workspace", "career_tags": "creative,media,technology", "order": 4},
        ],
    },
    {
        "text": "What motivates you most in your future career?",
        "category": "interest",
        "order": 4,
        "options": [
            {"text": "Solving complex technical problems", "career_tags": "technology,engineering,science", "order": 1},
            {"text": "Making a real difference in people's lives", "career_tags": "health,social,education", "order": 2},
            {"text": "Earning a high salary and financial security", "career_tags": "finance,business,law", "order": 3},
            {"text": "Having creative freedom and self-expression", "career_tags": "creative,media", "order": 4},
        ],
    },
    {
        "text": "Which of these best describes your natural talent?",
        "category": "strength",
        "order": 5,
        "options": [
            {"text": "I can understand and fix complex systems quickly", "career_tags": "technology,engineering", "order": 1},
            {"text": "I am very good at understanding and empathising with people", "career_tags": "health,social,education", "order": 2},
            {"text": "I love digging into data and spotting patterns", "career_tags": "finance,science,technology", "order": 3},
            {"text": "I have a gift for communicating and persuading", "career_tags": "law,creative,media,business", "order": 4},
        ],
    },
    {
        "text": "What type of problems do you find most satisfying to solve?",
        "category": "strength",
        "order": 6,
        "options": [
            {"text": "Engineering or coding challenges with logical solutions", "career_tags": "technology,engineering", "order": 1},
            {"text": "Social problems — poverty, inequality, or poor health", "career_tags": "social,health,governance", "order": 2},
            {"text": "Business problems around growth, profit, and strategy", "career_tags": "business,finance", "order": 3},
            {"text": "Creative problems — how to make something beautiful or compelling", "career_tags": "creative,media", "order": 4},
        ],
    },
    {
        "text": "How would your closest friends describe you?",
        "category": "personality",
        "order": 7,
        "options": [
            {"text": "The analytical one who always thinks logically", "career_tags": "technology,finance,science", "order": 1},
            {"text": "The caring one who always listens and supports", "career_tags": "health,social,education", "order": 2},
            {"text": "The leader who takes charge and organises", "career_tags": "business,governance,law", "order": 3},
            {"text": "The creative one who comes up with unique ideas", "career_tags": "creative,media", "order": 4},
        ],
    },
    {
        "text": "When working in a team, what role do you naturally gravitate to?",
        "category": "personality",
        "order": 8,
        "options": [
            {"text": "The technical expert solving the hard problems", "career_tags": "technology,engineering,science", "order": 1},
            {"text": "The mediator who keeps everyone working together", "career_tags": "social,governance,law", "order": 2},
            {"text": "The strategist planning what needs to happen", "career_tags": "business,finance", "order": 3},
            {"text": "The communicator presenting ideas clearly", "career_tags": "creative,media,education", "order": 4},
        ],
    },
    {
        "text": "Which future vision excites you the most?",
        "category": "values",
        "order": 9,
        "options": [
            {"text": "Building technology that millions of Kenyans use daily", "career_tags": "technology,engineering", "order": 1},
            {"text": "Running a clinic or hospital that serves my community", "career_tags": "health", "order": 2},
            {"text": "Leading a business, law firm, or government agency", "career_tags": "business,law,governance", "order": 3},
            {"text": "Creating a media brand, art studio, or creative agency", "career_tags": "creative,media", "order": 4},
        ],
    },
    {
        "text": "What are you willing to invest in your career?",
        "category": "values",
        "order": 10,
        "options": [
            {"text": "6+ years of study for a very specialised and high-paying career", "career_tags": "health,law,engineering", "order": 1},
            {"text": "4 years of focused university study in my passion area", "career_tags": "technology,business,science", "order": 2},
            {"text": "3 years of technical training to get into work quickly", "career_tags": "health,engineering,agriculture", "order": 3},
            {"text": "Learning by doing — building skills through projects and practice", "career_tags": "creative,technology,media", "order": 4},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed CareerProfile and quiz questions with real Kenyan career data"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")

    def handle(self, *args, **options):
        if options["clear"]:
            CareerProfile.objects.all().delete()
            QuizQuestion.objects.all().delete()
            self.stdout.write("Cleared existing career data.")

        # Seed career profiles
        created = 0
        for data in CAREERS:
            obj, c = CareerProfile.objects.update_or_create(
                title=data["title"],
                defaults={
                    "icon": data["icon"],
                    "demand_level": data["demand_level"],
                    "average_salary": data["average_salary"],
                    "career_tags": data["career_tags"],
                    "description": data["description"],
                    "duties": data["duties"],
                    "skills_required": data["skills_required"],
                    "educational_pathway": data["educational_pathway"],
                    "job_opportunities": data["job_opportunities"],
                    "future_outlook": data["future_outlook"],
                },
            )
            if c:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Career profiles: {created} created / {len(CAREERS) - created} updated ({len(CAREERS)} total)"
        ))

        # Seed quiz questions and options
        q_created = 0
        for qdata in QUIZ_QUESTIONS:
            question, qc = QuizQuestion.objects.get_or_create(
                text=qdata["text"],
                defaults={"category": qdata["category"], "order": qdata["order"]},
            )
            if qc:
                q_created += 1
                for odata in qdata["options"]:
                    QuizOption.objects.create(
                        question=question,
                        text=odata["text"],
                        career_tags=odata["career_tags"],
                        order=odata["order"],
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Quiz questions: {q_created} created ({len(QUIZ_QUESTIONS)} total)"
        ))
