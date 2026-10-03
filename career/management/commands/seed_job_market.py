"""
Seed JobMarketData with Kenya salary ranges.

Sources:
  - BrighterMonday Kenya Salary Report 2024 (brightermonday.co.ke/research)
  - KNBS Economic Survey 2024, Chapter 11 — Labour & Wages
  - Kenya Revenue Authority public salary schedule 2024
"""
from django.core.management.base import BaseCommand
from career.models import JobMarketData

CAREERS = [
    # ── Healthcare (University) ─────────────────────────────────────────────
    {
        'career_name': 'Medical Doctor',
        'keywords': 'doctor,physician,surgeon,medical officer,intern doctor,general practitioner,medicine,mbchb,bachelor of medicine,medicine and surgery',
        'salary_min': 200_000, 'salary_max': 400_000,
        'source_year': 2025,
        'source_name': 'KMPDU CBA — medical intern gross pay KSh ~206k (reported 2025)',
        'source_url': 'https://k24.digital/411/davji-atella-all-medical-interns-under-kmpdu-to-be-paid-ksh206k/amp',
        'demand': 'High',
        'top_sectors': 'Public Hospitals, Private Hospitals, NGOs, Research',
    },
    {
        'career_name': 'Dentist',
        'keywords': 'dentist,dental surgeon,dental surgery,oral health,orthodontist,dental officer',
        'salary_min': 100_000, 'salary_max': 350_000,
        'demand': 'Medium',
        'top_sectors': 'Private Practice, Hospitals, County Government',
    },
    {
        'career_name': 'Pharmacist',
        'keywords': 'pharmacist,pharmacy,pharmaceutical,drug,dispensing,clinical pharmacy',
        'salary_min': 80_000, 'salary_max': 200_000,
        'demand': 'High',
        'top_sectors': 'Retail Pharmacy, Hospitals, Pharmaceutical Manufacturing',
    },
    {
        'career_name': 'Clinical Officer',
        'keywords': 'clinical officer,clinical medicine,clinician,clinical medicine and surgery,orthopedic and trauma medicine,orthopedic trauma medicine,orthopaedic and trauma medicine',
        'salary_min': 105_900, 'salary_max': 338_010,
        'source_year': 2025,
        'source_name': 'KUCO–Council of Governors CBA 2025–2029 (county public-sector scale)',
        'source_url': 'https://www.kenyans.co.ke/news/120380-clinical-officers-earn-ksh338000-under-new-pay-deal',
        'demand': 'High',
        'top_sectors': 'Public Health, Private Clinics, NGOs, Mission Hospitals',
    },
    {
        'career_name': 'Registered Nurse',
        'keywords': 'nurse,nursing,registered nurse,midwife,midwifery,neonatal,paediatric nurse,psychiatric nurse,community health nursing',
        'salary_min': 40_000, 'salary_max': 100_000,
        'demand': 'High',
        'top_sectors': 'Hospitals, Clinics, NGOs, Schools',
    },
    {
        'career_name': 'Physiotherapist',
        'keywords': 'physiotherapist,physiotherapy,physical therapy,rehabilitation,physio',
        'salary_min': 50_000, 'salary_max': 130_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, Sports Clubs, Rehabilitation Centres',
    },
    {
        'career_name': 'Radiographer',
        'keywords': 'radiographer,radiography,radiology,imaging,x-ray,ct scan,mri',
        'salary_min': 50_000, 'salary_max': 130_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, Diagnostic Centres, Cancer Treatment Centres',
    },
    {
        'career_name': 'Medical Lab Technologist',
        'keywords': 'medical lab technologist,laboratory technologist,medical laboratory,medical laboratory science,medical laboratory sciences,medical laboratory technology,medical laboratory science and technology,lab scientist,haematology,microbiology lab,medical microbiology,biomedical science,biomedical sciences',
        'salary_min': 45_000, 'salary_max': 120_000,
        'demand': 'High',
        'top_sectors': 'Hospitals, Research Labs, Blood Banks, Public Health',
    },
    {
        'career_name': 'Medical Lab Technician',
        'keywords': 'medical lab technician,laboratory technician,lab technician,mlst',
        'salary_min': 30_000, 'salary_max': 70_000,
        'demand': 'High',
        'top_sectors': 'Hospitals, Private Labs, Clinics',
    },
    {
        'career_name': 'Pharmacy Technician',
        'keywords': 'pharmacy technician,pharmaceutical technician,dispenser',
        'salary_min': 30_000, 'salary_max': 75_000,
        'demand': 'Medium',
        'top_sectors': 'Community Pharmacy, Hospitals, Supermarket Pharmacies',
    },
    {
        'career_name': 'Nutritionist / Dietitian',
        'keywords': 'nutritionist,dietitian,nutrition,dietetics,nutrition and dietetics,food science and nutrition',
        'salary_min': 40_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, NGOs, Food Industry, Sports, Schools',
    },
    {
        'career_name': 'Public Health Officer',
        'keywords': 'public health officer,public health,environmental health,health inspector,epidemiology,community health officer,community health,community health and development,population health,health promotion,occupational health,global health,health education',
        'salary_min': 40_000, 'salary_max': 90_000,
        'demand': 'Medium',
        'top_sectors': 'County Government, NGOs, WHO, UNICEF, Ministry of Health',
    },
    {
        'career_name': 'Community Health Worker',
        'keywords': 'community health worker,community health promoter,chw,chp,community health assistant',
        'salary_min': 20_000, 'salary_max': 50_000,
        'demand': 'High',
        'top_sectors': 'County Health Departments, NGOs, USAID Projects',
    },
    {
        'career_name': 'Occupational Therapist',
        'keywords': 'occupational therapist,occupational therapy,rehabilitation therapist',
        'salary_min': 50_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, Rehabilitation Centres, Special Schools',
    },
    {
        'career_name': 'Veterinary Doctor',
        'keywords': 'veterinary,veterinarian,vet,veterinary medicine,veterinary surgery,veterinary medicine and surgery',
        'salary_min': 80_000, 'salary_max': 250_000,
        'demand': 'Medium',
        'top_sectors': 'Livestock & Agriculture, NGOs, Wildlife, Food Safety',
    },
    {
        'career_name': 'Health Records Officer',
        'keywords': 'health records,health information,medical records,hrio,health records and information,health records management,health informatics',
        'salary_min': 35_000, 'salary_max': 80_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, County Government, Insurance',
    },

    # ── Engineering & Technology ─────────────────────────────────────────────
    {
        'career_name': 'Software Developer',
        'keywords': 'software developer,software engineer,programmer,web developer,mobile developer,backend,frontend,full stack,application developer,software development,software engineering,computer science,computer,computing,computer studies,computer technology,computer systems,information technology,information systems,informatics,ict,information communication technology,information and communication technology',
        'salary_min': 60_000, 'salary_max': 300_000,
        'demand': 'High',
        'top_sectors': 'Tech Startups, Telecoms, Finance, E-Commerce, Consultancy',
    },
    {
        'career_name': 'Data Scientist',
        'keywords': 'data scientist,data analyst,machine learning,ai engineer,data engineer,business intelligence,bi analyst,data science,data analytics,data management,artificial intelligence,business analytics',
        'salary_min': 100_000, 'salary_max': 400_000,
        'demand': 'High',
        'top_sectors': 'Finance, Telecoms, Research Institutions, UN Agencies',
    },
    {
        'career_name': 'Network Engineer',
        'keywords': 'network engineer,network administrator,systems administrator,cybersecurity,cyber security,it security,network technician,cisco,cloud engineer,cloud computing,network,networks,computer networks,network and systems administration,information security,computer security',
        'salary_min': 60_000, 'salary_max': 200_000,
        'demand': 'High',
        'top_sectors': 'Telecoms, Banks, Government, IT Service Firms',
    },
    {
        'career_name': 'ICT Technician',
        'keywords': 'ict technician,computer technician,it support,ict support,helpdesk,desktop support,computer repair',
        'salary_min': 30_000, 'salary_max': 80_000,
        'demand': 'High',
        'top_sectors': 'Government, Schools, SMEs, Banks',
    },
    {
        'career_name': 'Civil Engineer',
        'keywords': 'civil engineer,civil engineering,structural engineer,structural engineering,civil and structural engineering,roads engineer,highways,highways engineering,infrastructure,drainage,geotechnical,road construction,roads',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'High',
        'top_sectors': 'KeNHA, County Government, Construction Firms, Consultancies',
    },
    {
        'career_name': 'Building Technician',
        'keywords': 'building technician,building technology,construction technician,site supervisor,clerk of works,building construction,building and construction,building and civil engineering',
        'salary_min': 35_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'Construction, Real Estate, County Government',
    },
    {
        'career_name': 'Electrical Engineer',
        'keywords': 'electrical engineer,power engineer,energy engineer,electrical engineering,electrical and electronic engineering,electrical and electronics engineering,electrical and telecommunication engineering,electrical and communication engineering,electrical and computer engineering,electronic and computer engineering,electrical power engineering,energy engineering,renewable energy,telecommunication,telecommunications,telecommunication engineering,telecommunication and information',
        'salary_min': 75_000, 'salary_max': 280_000,
        'demand': 'High',
        'top_sectors': 'Kenya Power, KETRACO, Manufacturing, Telecoms',
    },
    {
        'career_name': 'Electrical Technician',
        'keywords': 'electrical technician,electrician,electrical installation,electrical wiring,power technician,wireman,electrical wireman,electrical',
        'salary_min': 30_000, 'salary_max': 80_000,
        'demand': 'High',
        'top_sectors': 'Manufacturing, Construction, Utilities, Hotels',
    },
    {
        'career_name': 'Electronics Technician',
        'keywords': 'electronics technician,electronics,electronic engineering,consumer electronics,appliance repair,instrumentation,electrical and electronics,electrical and electronic technology,electrical and electronics technology',
        'salary_min': 28_000, 'salary_max': 75_000,
        'demand': 'Medium',
        'top_sectors': 'Manufacturing, Repair Services, Broadcast Media',
    },
    {
        'career_name': 'Mechanical Engineer',
        'keywords': 'mechanical engineer,manufacturing engineer,production engineer,mechanical engineering,mechanical,manufacturing,mechatronic,mechatronics,industrial technology,plant engineering,construction plant,plant and services engineering',
        'salary_min': 70_000, 'salary_max': 250_000,
        'demand': 'High',
        'top_sectors': 'Manufacturing, Oil & Gas, Automotive, Construction',
    },
    {
        'career_name': 'Automotive Technician',
        'keywords': 'automotive technician,motor vehicle technician,mechanic,mechanics,auto electrician,panel beater,automotive mechanic,motor vehicle,automotive,automobile,automotive engineering,vehicle engineering',
        'salary_min': 25_000, 'salary_max': 70_000,
        'demand': 'High',
        'top_sectors': 'Vehicle Dealerships, Garages, Public Transport, Fleet Companies',
    },
    {
        'career_name': 'Chemical Engineer',
        'keywords': 'chemical engineer,chemical engineering,chemical and process engineering,process engineering,process engineer,petrochemical,materials and metallurgical engineering,metallurgical',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'Medium',
        'top_sectors': 'Manufacturing, Oil & Gas, FMCG, Water Treatment',
    },
    {
        'career_name': 'Quantity Surveyor',
        'keywords': 'quantity surveyor,quantity surveying,qs,cost estimator,bills of quantities,construction cost',
        'salary_min': 70_000, 'salary_max': 250_000,
        'demand': 'High',
        'top_sectors': 'Construction, Real Estate, Government Projects',
    },
    {
        'career_name': 'Architect',
        'keywords': 'architect,architecture,architectural,building design',
        'salary_min': 90_000, 'salary_max': 350_000,
        'demand': 'Medium',
        'top_sectors': 'Architectural Firms, Real Estate, Government',
    },
    {
        'career_name': 'Land Surveyor',
        'keywords': 'land surveyor,survey,surveying,land survey,geomatics,geomatic,geomatic engineering,cartography,gis,geospatial,geographic information,geoinformatics,geo informatics,geoinformation,geospatial information science,photogrammetry,remote sensing',
        'salary_min': 70_000, 'salary_max': 200_000,
        'demand': 'Medium',
        'top_sectors': 'Survey of Kenya, County Government, Real Estate, Mining',
    },
    {
        'career_name': 'Plumber',
        'keywords': 'plumber,plumbing,pipefitter,sanitary,water systems',
        'salary_min': 25_000, 'salary_max': 70_000,
        'demand': 'Medium',
        'top_sectors': 'Construction, Hotels, Utilities, County Government',
    },
    {
        'career_name': 'Welder / Fabricator',
        'keywords': 'welder,fabricator,welding,metal fabrication,boilermaker,structural steel,metal processing',
        'salary_min': 25_000, 'salary_max': 65_000,
        'demand': 'Medium',
        'top_sectors': 'Manufacturing, Construction, Shipbuilding, Oil & Gas',
    },
    {
        'career_name': 'Refrigeration & AC Technician',
        'keywords': 'refrigeration,air conditioning,hvac,ac technician,cooling systems',
        'salary_min': 30_000, 'salary_max': 80_000,
        'demand': 'Medium',
        'top_sectors': 'Hotels, Supermarkets, Offices, Cold Chain Logistics',
    },
    {
        'career_name': 'Printing Technician',
        'keywords': 'printing technician,print,graphic printing,lithography,flexography,packaging',
        'salary_min': 25_000, 'salary_max': 65_000,
        'demand': 'Low',
        'top_sectors': 'Print Houses, Publishing, Packaging Industry',
    },

    # ── Business, Finance & Law ──────────────────────────────────────────────
    {
        'career_name': 'Accountant',
        'keywords': 'accountant,accounting,accountancy,cpa,financial accounting,management accounting,bookkeeper,accounts',
        'salary_min': 50_000, 'salary_max': 180_000,
        'demand': 'High',
        'top_sectors': 'Finance, NGOs, Government, FMCG, Audit Firms',
    },
    {
        'career_name': 'Auditor',
        'keywords': 'auditor,audit,internal audit,external audit,forensic accountant,compliance',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'High',
        'top_sectors': 'Audit Firms (Big 4), Banks, Government, Corporates',
    },
    {
        'career_name': 'Financial Analyst',
        'keywords': 'financial analyst,investment analyst,credit analyst,risk analyst,treasury,financial planning,finance,financial management,credit management,investment management,financial engineering,mathematics and finance',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'High',
        'top_sectors': 'Commercial Banks, Investment Firms, NSE, Insurance',
    },
    {
        'career_name': 'Actuary',
        'keywords': 'actuary,actuarial,actuarial science,insurance mathematics',
        'salary_min': 150_000, 'salary_max': 500_000,
        'demand': 'High',
        'top_sectors': 'Insurance, Pension Funds, Reinsurance, Consultancy',
    },
    {
        'career_name': 'Economist',
        'keywords': 'economist,economics,policy analyst,economic policy,macroeconomics,microeconomics,development economics,agricultural economics',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'Medium',
        'top_sectors': 'Government, Central Bank, World Bank, NGOs, Research',
    },
    {
        'career_name': 'Lawyer / Advocate',
        'keywords': 'lawyer,advocate,barrister,solicitor,legal,law,laws,llb,ll b,litigation,conveyancing,corporate law',
        'salary_min': 80_000, 'salary_max': 500_000,
        'demand': 'Medium',
        'top_sectors': 'Law Firms, Corporates, Government, NGOs, Judiciary',
    },
    {
        'career_name': 'Paralegal',
        'keywords': 'paralegal,legal assistant,law clerk,legal officer',
        'salary_min': 30_000, 'salary_max': 80_000,
        'demand': 'Medium',
        'top_sectors': 'Law Firms, NGOs, Government Ministries, Corporates',
    },
    {
        'career_name': 'Human Resources Officer',
        'keywords': 'human resources,hr,human resource management,personnel,recruitment,talent management,hrm,human reource,employment and labour',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'High',
        'top_sectors': 'All Sectors — universal demand across industries',
    },
    {
        'career_name': 'Marketing Manager',
        'keywords': 'marketing,brand manager,digital marketing,sales,marketing officer,advertising,e commerce,salesmanship',
        'salary_min': 60_000, 'salary_max': 300_000,
        'demand': 'High',
        'top_sectors': 'FMCG, Telecoms, Banking, Retail, Agencies',
    },
    {
        'career_name': 'Supply Chain Officer',
        'keywords': 'supply chain,logistics,procurement,purchasing,inventory,warehouse,distribution,stores,storekeeping,supplies,supplies management,freight,transport management,transport,air cargo',
        'salary_min': 50_000, 'salary_max': 180_000,
        'demand': 'High',
        'top_sectors': 'Manufacturing, Retail, NGOs, Healthcare, Government',
    },
    {
        'career_name': 'Business Analyst',
        'keywords': 'business analyst,business development,management consultant,strategy,operations analyst',
        'salary_min': 80_000, 'salary_max': 280_000,
        'demand': 'High',
        'top_sectors': 'Finance, Telecoms, Consulting Firms, Tech Companies',
    },
    {
        'career_name': 'Insurance Officer',
        'keywords': 'insurance,underwriter,claims,insurance agent,insurance sales,reinsurance',
        'salary_min': 40_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'Insurance Companies, Brokers, Bancassurance',
    },
    {
        'career_name': 'Bank Teller / Officer',
        'keywords': 'bank teller,bank officer,banking,customer service banking,teller',
        'salary_min': 35_000, 'salary_max': 80_000,
        'demand': 'Medium',
        'top_sectors': 'Commercial Banks, Microfinance, Saccos',
    },
    {
        'career_name': 'Procurement Officer',
        'keywords': 'procurement officer,purchasing officer,supply officer,tender,public procurement',
        'salary_min': 60_000, 'salary_max': 180_000,
        'demand': 'High',
        'top_sectors': 'Government, NGOs, UN Agencies, Hospitals, Corporates',
    },

    # ── Education & Social Sciences ──────────────────────────────────────────
    {
        'career_name': 'Secondary School Teacher',
        'keywords': 'secondary teacher,high school teacher,tsc teacher,secondary education,form teacher,teacher education,teachers education,secondary teacher education,secondary teachers education,bachelor of education,with education,technical education,technology education,music education,special needs education,special education',
        'salary_min': 50_000, 'salary_max': 130_000,
        'source_year': 2025,
        'source_name': 'TSC CBA 2025–2029 — grades C2–D2 basic pay plus house & commuter allowances',
        'source_url': 'https://www.kenyans.co.ke/news/114320-teachers-earn-ksh167k-tsc-signs-new-cba',
        'demand': 'High',
        'top_sectors': 'Public Schools (TSC), Private Schools, International Schools',
    },
    {
        'career_name': 'Primary School Teacher',
        'keywords': 'primary teacher,primary school,p1 teacher,upper primary,lower primary,primary teacher education,primary education,art and craft education',
        'salary_min': 25_000, 'salary_max': 60_000,
        'demand': 'High',
        'top_sectors': 'Public Schools (TSC), Private Schools, Community Schools',
    },
    {
        'career_name': 'ECD Teacher',
        'keywords': 'ecd teacher,early childhood,nursery teacher,pre-school,kindergarten,pp1,pp2,education early childhood,education in early childhood,early childhood and primary education,early childhood development education',
        'salary_min': 20_000, 'salary_max': 50_000,
        'demand': 'High',
        'top_sectors': 'County Government, Private Schools, NGOs',
    },
    {
        'career_name': 'University Lecturer',
        'keywords': 'lecturer,professor,university teaching,academic,tutor,academic staff',
        'salary_min': 100_000, 'salary_max': 300_000,
        'demand': 'Medium',
        'top_sectors': 'Public Universities, Private Universities, Research Institutes',
    },
    {
        'career_name': 'Social Worker',
        'keywords': 'social worker,social work,community development,community organiser,welfare officer,probation,child care,childcare,child protection,child care and protection,child and youth,social development',
        'salary_min': 35_000, 'salary_max': 90_000,
        'demand': 'Medium',
        'top_sectors': 'NGOs, County Government, Hospitals, Prison Service',
    },
    {
        'career_name': 'Psychologist / Counsellor',
        'keywords': 'psychologist,counsellor,counselor,psychology,mental health,guidance counsellor,therapist,counselling,counseling,health counselling,guidance and counselling',
        'salary_min': 60_000, 'salary_max': 200_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, NGOs, Schools, Corporates, Private Practice',
    },
    {
        'career_name': 'Librarian',
        'keywords': 'librarian,library,information science,information sciences,information studies,records management,records and archives,archives,archivist,knowledge management,records management and information',
        'salary_min': 35_000, 'salary_max': 90_000,
        'demand': 'Low',
        'top_sectors': 'Universities, Schools, Government Ministries, Kenya National Archives',
    },

    # ── Agriculture & Environment ────────────────────────────────────────────
    {
        'career_name': 'Agronomist',
        'keywords': 'agronomist,agronomy,crop scientist,crop production,agriculture,agricultural,agribusiness,agripreneurship,crop,crop protection,crop improvement,soil scientist,soil science,soil management,soils,crop extension,seed science,food security,farm business,farm',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Agriculture Companies, NGOs, KARI, Export Horticulture',
    },
    {
        'career_name': 'Agricultural Extension Officer',
        'keywords': 'agricultural extension,extension officer,agricultural officer,farm extension,agricultural education',
        'salary_min': 40_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'County Government, NGOs, Input Companies, Cooperatives',
    },
    {
        'career_name': 'Food Scientist',
        'keywords': 'food scientist,food science,food technology,food quality,food processing,food safety,food production,food operations,dairy technology,dairy processing,animal products technology,agro processing,food systems',
        'salary_min': 60_000, 'salary_max': 180_000,
        'demand': 'Medium',
        'top_sectors': 'FMCG, Food Processing, KEBS, Export Companies',
    },
    {
        'career_name': 'Horticulturist',
        'keywords': 'horticulturist,horticulture,floriculture,flower grower,greenhouse,fruit production',
        'salary_min': 45_000, 'salary_max': 140_000,
        'demand': 'Medium',
        'top_sectors': 'Cut Flower Farms, Export Agriculture, Supermarket Chains',
    },
    {
        'career_name': 'Environmental Scientist',
        'keywords': 'environmental scientist,environmental management,environmental impact,nema,waste management,ecology,environmental science,environmental sciences,enviromental science,environmental technology,environmental studies,environmental resource,environmental conservation,natural resource,natural resources,natural resource management,natural resources management,resource conservation,bio resources,climate change,earth science,earth sciences,environment,dryland,arid lands,agro ecosystem,marine resource,coastal and marine resource,geography,sustainability',
        'salary_min': 60_000, 'salary_max': 180_000,
        'demand': 'Medium',
        'top_sectors': 'NEMA, NGOs, Mining, Energy, Consultancy',
    },
    {
        'career_name': 'Forestry Officer',
        'keywords': 'forestry officer,forester,forest,forestry,agroforestry,kfs,afforestation,tree planting,wood science',
        'salary_min': 45_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'Kenya Forest Service, County Government, NGOs, Carbon Credits',
    },
    {
        'career_name': 'Fisheries Officer',
        'keywords': 'fisheries officer,fisheries,aquaculture,fish farming,marine science,marine biology,aquatic',
        'salary_min': 40_000, 'salary_max': 100_000,
        'demand': 'Low',
        'top_sectors': 'Government, Aquaculture Farms, NGOs, Lake Victoria Fisheries',
    },
    {
        'career_name': 'Animal Production Officer',
        'keywords': 'animal production,animal health,animal health and production,livestock,animal science,zootechnician,animal husbandry,dairy,range management,rangeland,poultry,apiculture,beekeeping',
        'salary_min': 40_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'County Government, Dairy Companies, Livestock NGOs, Ranches',
    },

    # ── Hospitality & Tourism ────────────────────────────────────────────────
    {
        'career_name': 'Hotel Manager',
        'keywords': 'hotel manager,hospitality management,hotel management,lodge manager,resort manager,food and beverage manager,hotel,hospitality,institutional management,housekeeping management',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'Medium',
        'top_sectors': 'Hotels, Safari Lodges, Beach Resorts, Restaurant Chains',
    },
    {
        'career_name': 'Chef',
        'keywords': 'chef,cook,culinary,pastry chef,food preparation,sous chef,baking,baking technology,pastry,bakery',
        'salary_min': 35_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'Hotels, Restaurants, Airlines, Offshore Catering, Events',
    },
    {
        'career_name': 'Catering Technician',
        'keywords': 'catering technician,food and beverage,food beverage,catering,waitstaff,banqueting,hospitality operations,housekeeping,laundry,front office',
        'salary_min': 22_000, 'salary_max': 60_000,
        'demand': 'Medium',
        'top_sectors': 'Hotels, Institutions, Outdoor Catering, Hospitals',
    },
    {
        'career_name': 'Tour Guide / Tourism Officer',
        'keywords': 'tour guide,tourism officer,tourist guide,safari guide,travel,ecotourism,eco tourism,park ranger,tour guiding,tour administration,nature interpretation',
        'salary_min': 30_000, 'salary_max': 80_000,
        'demand': 'Medium',
        'top_sectors': 'Tour Operators, KWS, Hotels, Airlines, Cruise Lines',
    },
    {
        'career_name': 'Travel Agent',
        'keywords': 'travel agent,ticketing,airline reservations,tourism,iata,travel consultant',
        'salary_min': 30_000, 'salary_max': 80_000,
        'demand': 'Medium',
        'top_sectors': 'Tour Operators, Airlines, MICE Companies, Online Travel',
    },
    {
        'career_name': 'Event Manager',
        'keywords': 'event manager,events organiser,conference organiser,mice,wedding planner,event coordinator,events management,events,event and convention management',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Event Companies, Hotels, NGOs, Corporates, Government',
    },

    # ── Creative, Design & Media ─────────────────────────────────────────────
    {
        'career_name': 'Graphic Designer',
        'keywords': 'graphic designer,graphic design,graphics design,graphic and web design,printing,printing technology,visual designer,ui designer,ux designer,brand designer,typographer,design',
        'salary_min': 40_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Advertising Agencies, Media Houses, Tech Companies, Freelance',
    },
    {
        'career_name': 'Journalist',
        'keywords': 'journalist,reporter,news,media,broadcast,photojournalist,editor,sub-editor,journalism,digital journalism,mass communication,communication,communication studies,broadcasting,media technology',
        'salary_min': 35_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'TV Stations, Newspapers, Online Media, NGOs',
    },
    {
        'career_name': 'Public Relations Officer',
        'keywords': 'public relations,pr officer,communications officer,corporate affairs,media relations,spokesperson,corporate communication,public communication',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Corporates, Government, NGOs, PR Agencies',
    },
    {
        'career_name': 'Film & TV Producer',
        'keywords': 'filmmaker,film producer,video producer,videographer,cinematographer,director,media production,broadcast production,film,film production,film technology,television,television production,video production,programmes production,animation,gaming',
        'salary_min': 40_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'TV Stations, Advertising, NGOs, Streaming Platforms',
    },
    {
        'career_name': 'Interior Designer',
        'keywords': 'interior designer,interior design,interior decorator,space planning',
        'salary_min': 50_000, 'salary_max': 180_000,
        'demand': 'Medium',
        'top_sectors': 'Real Estate, Construction, Hotels, High-end Retail',
    },
    {
        'career_name': 'Fashion Designer',
        'keywords': 'fashion designer,fashion design,fashion,clothing design,clothing,clothing technology,apparel,textile,garment design,costume',
        'salary_min': 30_000, 'salary_max': 100_000,
        'demand': 'Low',
        'top_sectors': 'Fashion Houses, Export Industry, Entertainment, Retail',
    },

    # ── Trades & Artisan (TVET) ──────────────────────────────────────────────
    {
        'career_name': 'Hairdresser / Cosmetologist',
        'keywords': 'hairdresser,hairdressing,hair dressing,cosmetologist,beautician,hair stylist,barber,cosmetology,beauty therapy,nail technician',
        'salary_min': 20_000, 'salary_max': 60_000,
        'demand': 'Medium',
        'top_sectors': 'Salons, Hotels, Spas, Freelance, TV Production',
    },
    {
        'career_name': 'Tailor / Garment Maker',
        'keywords': 'tailor,tailoring,garment,garment making,sewing,dressmaker,dressmaking,knitting,clothing production,fashion artisan',
        'salary_min': 20_000, 'salary_max': 60_000,
        'demand': 'Medium',
        'top_sectors': 'Garment Factories, Export, Fashion, Freelance',
    },
    {
        'career_name': 'Carpenter / Joiner',
        'keywords': 'carpenter,carpentry,joinery,cabinet maker,furniture maker,furniture,woodwork,wood technology',
        'salary_min': 25_000, 'salary_max': 70_000,
        'demand': 'Medium',
        'top_sectors': 'Furniture Industry, Construction, Real Estate',
    },
    {
        'career_name': 'Mason / Builder',
        'keywords': 'mason,masonry,bricklayer,builder,concrete,artisan builder',
        'salary_min': 25_000, 'salary_max': 70_000,
        'demand': 'High',
        'top_sectors': 'Construction Industry, Real Estate, County Government',
    },

    # ── Specialised Professions ──────────────────────────────────────────────
    {
        'career_name': 'Pilot',
        'keywords': 'pilot,aviation,flight,airline pilot,commercial pilot,air transport',
        'salary_min': 200_000, 'salary_max': 800_000,
        'demand': 'High',
        'top_sectors': 'Kenya Airways, Private Airlines, Cargo, Charter Flights',
    },
    {
        'career_name': 'Air Traffic Controller',
        'keywords': 'air traffic controller,atc,air traffic,kcaa,aviation safety',
        'salary_min': 150_000, 'salary_max': 500_000,
        'demand': 'Medium',
        'top_sectors': 'KCAA, Kenya Airports Authority, Military Aviation',
    },
    {
        'career_name': 'Marine Engineer',
        'keywords': 'marine engineer,marine engineering,maritime,shipping,naval,offshore,port management,marine transportation,nautical,nautical science,seafarers',
        'salary_min': 100_000, 'salary_max': 400_000,
        'demand': 'Medium',
        'top_sectors': 'Shipping Companies, KPA, Kenya Navy, Oil & Gas',
    },
    {
        'career_name': 'Geologist',
        'keywords': 'geologist,geology,mining engineer,mining,mineral,minerals,mineral processing,petroleum,petroleum engineering,petroleum geologist,geoscience,geosciences,mineralogy,hydrogeologist',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'Medium',
        'top_sectors': 'Mining, Oil & Gas, NEMA, Water Resources, Consultancy',
    },
    {
        'career_name': 'Meteorologist',
        'keywords': 'meteorologist,meteorology,weather,climate scientist,climatologist,atmospheric science',
        'salary_min': 60_000, 'salary_max': 200_000,
        'demand': 'Low',
        'top_sectors': 'Kenya Meteorological Dept, ICPAC, Aviation, Research',
    },
    {
        'career_name': 'Statistician',
        'keywords': 'statistician,statistics,biostatistics,quantitative analyst,data collection,applied statistics',
        'salary_min': 60_000, 'salary_max': 200_000,
        'demand': 'Medium',
        'top_sectors': 'KNBS, Government, Banks, Research Institutions, UN Agencies',
    },
    {
        'career_name': 'Military Officer',
        'keywords': 'military officer,army,navy,air force,kdf,defence,officer cadet',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Kenya Defence Forces, Police Service, NYS',
    },
]

# ── Fields added Oct 2026 ─────────────────────────────────────────────────────
# No dedicated salary survey row exists for these; ranges are estimates set
# against comparable BrighterMonday 2024 rows above and the KNBS Economic
# Survey 2026 average wage (~KSh 82k/month in 2025), and are labelled as such.
ESTIMATE_SOURCE = {
    'source_year': 2025,
    'source_name': 'KUCCPSS estimate — benchmarked to BrighterMonday 2024 & KNBS Economic Survey 2026',
    'source_url':  'https://www.knbs.or.ke',
}

ESTIMATED_CAREERS = [
    # ── Technician-level equivalents (used for diploma/certificate courses) ──
    {
        'career_name': 'Mechanical Technician',
        'keywords': 'mechanical technician,fitter,general fitter,general fitters,lathe machine,machine operator,machinist,machining',
        'salary_min': 30_000, 'salary_max': 85_000,
        'demand': 'Medium',
        'top_sectors': 'Manufacturing, Sugar & Tea Factories, KenGen, Construction, Workshops',
    },
    {
        'career_name': 'Civil Engineering Technician',
        'keywords': 'civil engineering technician,civil technician,roads technician',
        'salary_min': 35_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'KeNHA, KURA, KeRRA, County Governments, Contractors',
    },
    {
        'career_name': 'Science Laboratory Technologist',
        'keywords': 'science laboratory technologist,science laboratory technology,science lab technology,science lab,laboratory science,laboratory sciences,laboratory technology,laboratory science and technology,animal laboratory,water and wastewater laboratory,water and waste water laboratory',
        'salary_min': 30_000, 'salary_max': 90_000,
        'demand': 'Medium',
        'top_sectors': 'Schools & Universities, KEBS, Research Institutes, Manufacturing, Water Companies',
    },
    # ── Engineering & Technical ───────────────────────────────────────────────
    {
        'career_name': 'Aeronautical Engineer / Aircraft Technician',
        'keywords': 'aeronautical,aeronautical engineering,aerospace,aerospace engineering,avionics,airframes,aircraft maintenance',
        'salary_min': 60_000, 'salary_max': 250_000,
        'demand': 'Medium',
        'top_sectors': 'Kenya Airways, KCAA, Kenya Air Force, MROs, Charter Airlines',
    },
    {
        'career_name': 'Aviation Operations Officer',
        'keywords': 'flight operations,flight dispatch,airport operations,aviation management,civil aviation management',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Kenya Airports Authority, Airlines, Ground Handlers, KCAA',
    },
    {
        'career_name': 'Biomedical Engineering Technologist',
        'keywords': 'biomedical engineering,medical engineering,medical engineering technology,medical equipment',
        'salary_min': 40_000, 'salary_max': 150_000,
        'demand': 'High',
        'top_sectors': 'Public & Private Hospitals, Medical Equipment Suppliers, MoH',
    },
    {
        'career_name': 'Agricultural Engineer',
        'keywords': 'agricultural engineering,agricultural engineer,biosystems engineering,bio systems engineering,agricultural and biosystems engineering,agricultural and bio systems engineering',
        'salary_min': 60_000, 'salary_max': 200_000,
        'demand': 'Medium',
        'top_sectors': 'Irrigation Authority, Agro-processors, County Governments, NGOs',
    },
    {
        'career_name': 'Water Engineer / Technologist',
        'keywords': 'water engineering,water technology,water and sanitation,water sanitation,water resources,water resource,water resource management,water and environment,water and environmental engineering,water and irrigation,irrigation,hydrology,water operators,water engineer',
        'salary_min': 45_000, 'salary_max': 180_000,
        'demand': 'High',
        'top_sectors': 'Water Service Providers, WRA, Irrigation Authority, County Governments, NGOs',
    },
    {
        'career_name': 'Construction Manager',
        'keywords': 'construction management,construction manager,site manager',
        'salary_min': 70_000, 'salary_max': 250_000,
        'demand': 'Medium',
        'top_sectors': 'Contractors, Real Estate Developers, NHC, Consultancies',
    },
    {
        'career_name': 'Leather Technologist',
        'keywords': 'leather,leather technology,leatherwork,tannery',
        'salary_min': 25_000, 'salary_max': 80_000,
        'demand': 'Low',
        'top_sectors': 'Tanneries, Footwear Manufacturing, Kenya Leather Development Council',
    },
    {
        'career_name': 'Firefighter',
        'keywords': 'firefighter,fire fighter,firefighting,fire safety',
        'salary_min': 30_000, 'salary_max': 80_000,
        'demand': 'Medium',
        'top_sectors': 'County Fire Services, KAA, Industrial Plants, Oil & Gas',
    },
    # ── Natural & Physical Sciences ──────────────────────────────────────────
    {
        'career_name': 'Chemist',
        'keywords': 'chemist,chemistry,analytical chemistry,industrial chemistry,applied chemistry,polymer chemistry,petroleum chemistry,environmental chemistry,industrial and applied chemistry',
        'salary_min': 50_000, 'salary_max': 180_000,
        'demand': 'Medium',
        'top_sectors': 'Manufacturing, Government Chemist, KEBS, KEMRI, Pharmaceuticals',
    },
    {
        'career_name': 'Physicist',
        'keywords': 'physicist,physics,applied physics,engineering physics,mining physics,geophysics,astrophysics,astronomy,optics,lasers,environmental physics,technical and applied physics',
        'salary_min': 50_000, 'salary_max': 180_000,
        'demand': 'Low',
        'top_sectors': 'Research Institutes, Energy, KEBS, Telecoms, Universities',
    },
    {
        'career_name': 'Biologist / Research Scientist',
        'keywords': 'biologist,biology,applied biology,biological sciences,botany,zoology,ethnobotany,entomology,parasitology,conservation biology,molecular biology,cellular biology,genomic,genomics,biosafety,biosecurity',
        'salary_min': 45_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'KEMRI, KALRO, ICIPE, KWS, Universities, NGOs',
    },
    {
        'career_name': 'Biochemist / Biotechnologist',
        'keywords': 'biochemist,biochemistry,biotechnology,biotechnologist,microbiology,medical biochemistry,industrial biotechnology,medical biotechnology,bioengineering,nutraceutical',
        'salary_min': 50_000, 'salary_max': 180_000,
        'demand': 'Medium',
        'top_sectors': 'KEMRI, Pharmaceuticals, Breweries & Food Industry, ILRI, Research Labs',
    },
    {
        'career_name': 'Forensic Scientist',
        'keywords': 'forensic science,forensic biology,forensic technology,forensic scientist',
        'salary_min': 60_000, 'salary_max': 180_000,
        'demand': 'Medium',
        'top_sectors': 'Government Chemist, DCI Forensics Lab, Private Labs',
    },
    {
        'career_name': 'Mathematician',
        'keywords': 'mathematician,mathematics,mathematical sciences,industrial mathematics,applied mathematics,pure mathematics,operations research,modelling',
        'salary_min': 50_000, 'salary_max': 200_000,
        'demand': 'Medium',
        'top_sectors': 'Banks, Insurance, Research, Tech Companies, Teaching',
    },
    {
        'career_name': 'Wildlife / Conservation Officer',
        'keywords': 'wildlife,wildlife management,community wildlife,wildlife conservation,parks,conservationist',
        'salary_min': 40_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'KWS, Conservancies, WWF, Tour Operators, County Governments',
    },
    {
        'career_name': 'Urban & Regional Planner',
        'keywords': 'urban planner,urban and regional planning,regional planning,planning,spatial planning,spacial planning,urban design,urban,land use,land resource planning,environmental planning,built environment',
        'salary_min': 60_000, 'salary_max': 200_000,
        'demand': 'Medium',
        'top_sectors': 'County Governments, Ministry of Lands, Consultancies, UN-Habitat',
    },
    {
        'career_name': 'Real Estate Manager / Valuer',
        'keywords': 'real estate,valuer,valuation,property management,estate management,land and estate management,land administration',
        'salary_min': 60_000, 'salary_max': 250_000,
        'demand': 'Medium',
        'top_sectors': 'Real Estate Firms, Banks, Ministry of Lands, Property Developers',
    },
    # ── Health (KMTC & allied) ───────────────────────────────────────────────
    {
        'career_name': 'Optometrist',
        'keywords': 'optometrist,optometry,vision sciences,optometry and vision sciences',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Eye Hospitals, Optical Retail, County Hospitals, NGOs',
    },
    {
        'career_name': 'Paramedic / Emergency Medical Technician',
        'keywords': 'paramedic,paramedic science,emergency medical,emergency medical technology,medical emergency technician,emergency medical technician',
        'salary_min': 35_000, 'salary_max': 100_000,
        'demand': 'High',
        'top_sectors': 'Kenya Red Cross, St John Ambulance, AMREF Flying Doctors, Hospitals',
    },
    {
        'career_name': 'Dental Technologist',
        'keywords': 'dental technology,dental technologist,dental technician',
        'salary_min': 35_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'Dental Labs, Hospitals, Private Dental Clinics',
    },
    {
        'career_name': 'Orthopaedic Technologist',
        'keywords': 'orthopaedic technology,orthopedic technology,orthopaedic technologist,prosthetics,orthotics',
        'salary_min': 40_000, 'salary_max': 110_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, Rehabilitation Centres, APDK, NGOs',
    },
    {
        'career_name': 'Speech & Language Therapist',
        'keywords': 'speech and language therapy,speech therapy,speech therapist,audiology',
        'salary_min': 50_000, 'salary_max': 130_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, Special Schools, Rehabilitation Centres, Private Practice',
    },
    {
        'career_name': 'Mortician',
        'keywords': 'mortuary,mortuary science,mortician,funeral',
        'salary_min': 25_000, 'salary_max': 70_000,
        'demand': 'Medium',
        'top_sectors': 'Hospital Mortuaries, Funeral Homes, County Governments',
    },
    {
        'career_name': 'Health Services Manager',
        'keywords': 'health services management,health systems management,health management,hospital management,health systems',
        'salary_min': 70_000, 'salary_max': 250_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, County Health Departments, NHIF/SHA, NGOs',
    },
    {
        'career_name': 'Sports Scientist / Coach',
        'keywords': 'sports science,sport science,sports management,sports,exercise,fitness,fitness instruction,recreation,physical education,sports scientist,coach',
        'salary_min': 35_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'Sports Clubs, Gyms, Schools, Sports Kenya, Federations',
    },
    # ── Business & Administration ────────────────────────────────────────────
    {
        'career_name': 'Business Manager / Administrator',
        'keywords': 'business administration,business management,business information and management,business and management,business studies,commerce,business leadership,international business,strategic management,organizational management,management and leadership,leadership and management,leadership,liberal studies,diploma in management,office management,business and office management',
        'salary_min': 50_000, 'salary_max': 200_000,
        'demand': 'Medium',
        'top_sectors': 'Corporates, Banks, SMEs, NGOs, Government',
    },
    {
        'career_name': 'Entrepreneur / SME Manager',
        'keywords': 'entrepreneur,entrepreneurship,entreprenuership,enterprise management,small business,small and micro enterprises,small enterprises,enterprise development,business innovation',
        'salary_min': 40_000, 'salary_max': 200_000,
        'demand': 'Medium',
        'top_sectors': 'Self-employment, SMEs, KIE, Youth & Women Enterprise Funds',
    },
    {
        'career_name': 'Project Manager',
        'keywords': 'project manager,project management,project planning,project planning and management,project development,energy project management',
        'salary_min': 70_000, 'salary_max': 250_000,
        'demand': 'High',
        'top_sectors': 'NGOs, Construction, Telecoms, Energy, Government Projects',
    },
    {
        'career_name': 'Tax / Customs Officer',
        'keywords': 'tax administration,customs administration,revenue administration,customs,tax officer,revenue officer',
        'salary_min': 50_000, 'salary_max': 180_000,
        'demand': 'Medium',
        'top_sectors': 'KRA, Clearing & Forwarding Firms, County Revenue Departments, Audit Firms',
    },
    {
        'career_name': 'Co-operative Officer',
        'keywords': 'co operative,co operatives,cooperative,cooperatives,cooperative management,co operative management,co operative business',
        'salary_min': 40_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'SACCOs, Co-operative Societies, State Department for Co-operatives',
    },
    {
        'career_name': 'Office Administrator / Secretary',
        'keywords': 'secretary,secretarial,secretarial studies,secretarial management,office administration,office assistance,clerical,clerical operations,clerk,clerk typist,typist,computerized secretarial',
        'salary_min': 25_000, 'salary_max': 75_000,
        'demand': 'Medium',
        'top_sectors': 'Government Offices, Corporates, Schools, Law Firms, NGOs',
    },
    # ── Social Sciences, Law & Governance ────────────────────────────────────
    {
        'career_name': 'Criminologist / Security Officer',
        'keywords': 'criminology,criminologist,criminal justice,security studies,security management,security science,security and intelligence,intelligence,penology,phenology,correction,corrections,security officer',
        'salary_min': 45_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Kenya Prisons, National Police Service, NIS, Private Security, Banks',
    },
    {
        'career_name': 'Public Administrator / Policy Officer',
        'keywords': 'public administration,public policy,public management,public management and development,governance,county governance,corporate governance,political science,policy studies,public administrator',
        'salary_min': 50_000, 'salary_max': 180_000,
        'demand': 'Medium',
        'top_sectors': 'National & County Government, Parliament, NGOs, Think Tanks',
    },
    {
        'career_name': 'Diplomat / International Relations Officer',
        'keywords': 'international relations,diplomacy,international diplomacy,international studies,diplomat,peace,peace studies,peace and conflict,conflict,conflict resolution,conflict management,peace education,justice and peace',
        'salary_min': 60_000, 'salary_max': 250_000,
        'demand': 'Low',
        'top_sectors': 'Ministry of Foreign Affairs, UN Agencies, AU, IGAD, Embassies, NGOs',
    },
    {
        'career_name': 'Disaster Management Officer',
        'keywords': 'disaster management,disaster,disaster preparedness,disaster mitigation,disaster risk,emergency management,humanitarian assistance,humanitarian',
        'salary_min': 45_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Kenya Red Cross, NDMA, UN Agencies, County Governments, NGOs',
    },
    {
        'career_name': 'Development / Programme Officer',
        'keywords': 'development studies,development officer,programme officer,gender,gender and development,sociology,anthropology,medical anthropology,human rights,sustainable human development,strategic development,developmental and policy studies,community resource management,social studies',
        'salary_min': 45_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'NGOs, UN Agencies, County Governments, Research Institutions',
    },
    # ── Arts, Languages & Religion ───────────────────────────────────────────
    {
        'career_name': 'Linguist / Translator',
        'keywords': 'linguist,linguistics,linguistic,translation,translator,interpreter,english,kiswahili,french,german,arabic,mandarin,literature,languages,english language',
        'salary_min': 40_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Media, UN & Embassies, Publishing, Translation Agencies, Teaching',
    },
    {
        'career_name': 'Historian / Heritage Officer',
        'keywords': 'historian,history,archaeology,heritage,museum,museum studies',
        'salary_min': 40_000, 'salary_max': 120_000,
        'demand': 'Low',
        'top_sectors': 'National Museums of Kenya, Kenya National Archives, Research, Teaching',
    },
    {
        'career_name': 'Clergy / Chaplain',
        'keywords': 'theology,theologian,divinity,biblical,bible,pastoral,chaplaincy,chaplain,religious studies,religion,christian education,church,islamic studies,islamic sharia,sharia,inter cultural studies,intercultural studies',
        'salary_min': 30_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'Churches & Mosques, Faith-based NGOs, Schools, Hospitals, Military Chaplaincy',
    },
    {
        'career_name': 'Musician / Performing Artist',
        'keywords': 'music,musician,music production,music technology,music theory,performing arts,music and dance,dance,theatre,theater,drama,theatre arts,drama and theatre',
        'salary_min': 25_000, 'salary_max': 150_000,
        'demand': 'Low',
        'top_sectors': 'Entertainment, Media Houses, Churches, Events, Kenya Music Festival',
    },
    {
        'career_name': 'Fine Artist / Illustrator',
        'keywords': 'fine art,fine arts,art and design,illustrator,artist',
        'salary_min': 25_000, 'salary_max': 120_000,
        'demand': 'Low',
        'top_sectors': 'Advertising Agencies, Galleries, Publishing, Self-employment',
    },
]

for _entry in ESTIMATED_CAREERS:
    for _k, _v in ESTIMATE_SOURCE.items():
        _entry.setdefault(_k, _v)
CAREERS += ESTIMATED_CAREERS

SOURCE_DEFAULTS = {
    'source_year': 2024,
    'source_name': 'BrighterMonday Kenya Salary Report 2024',
    'source_url':  'https://www.brightermonday.co.ke/research',
}


class Command(BaseCommand):
    help = 'Seed JobMarketData with Kenya salary intelligence (BrighterMonday 2024 + KNBS 2024)'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Delete all existing records before seeding')

    def handle(self, *args, **options):
        if options['clear']:
            deleted, _ = JobMarketData.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing records.'))

        created = updated = 0
        for entry in CAREERS:
            data = {**SOURCE_DEFAULTS, **entry}
            _, was_created = JobMarketData.objects.update_or_create(
                career_name=data.pop('career_name'),
                defaults=data,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created: {created}  Updated: {updated}  '
            f'Total records: {JobMarketData.objects.count()}'
        ))
