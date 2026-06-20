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
        'keywords': 'doctor,physician,surgeon,medical officer,intern doctor,general practitioner,specialist,medicine,mbchb',
        'salary_min': 100_000, 'salary_max': 400_000,
        'demand': 'High',
        'top_sectors': 'Public Hospitals, Private Hospitals, NGOs, Research',
    },
    {
        'career_name': 'Dentist',
        'keywords': 'dentist,dental surgeon,oral health,orthodontist,dental officer',
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
        'keywords': 'clinical officer,clinical medicine,clinician',
        'salary_min': 45_000, 'salary_max': 120_000,
        'demand': 'High',
        'top_sectors': 'Public Health, Private Clinics, NGOs, Mission Hospitals',
    },
    {
        'career_name': 'Registered Nurse',
        'keywords': 'nurse,nursing,registered nurse,midwife,midwifery,neonatal,paediatric nurse,psychiatric nurse',
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
        'keywords': 'medical lab technologist,laboratory technologist,medical laboratory,lab scientist,haematology,microbiology lab',
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
        'keywords': 'nutritionist,dietitian,nutrition,food science,dietetics',
        'salary_min': 40_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, NGOs, Food Industry, Sports, Schools',
    },
    {
        'career_name': 'Public Health Officer',
        'keywords': 'public health officer,public health,environmental health,health inspector,epidemiology,community health officer',
        'salary_min': 40_000, 'salary_max': 90_000,
        'demand': 'Medium',
        'top_sectors': 'County Government, NGOs, WHO, UNICEF, Ministry of Health',
    },
    {
        'career_name': 'Community Health Worker',
        'keywords': 'community health worker,community health promoter,chw,chp',
        'salary_min': 20_000, 'salary_max': 50_000,
        'demand': 'High',
        'top_sectors': 'County Health Departments, NGOs, USAID Projects',
    },
    {
        'career_name': 'Occupational Therapist',
        'keywords': 'occupational therapist,occupational therapy,ot,rehabilitation therapist',
        'salary_min': 50_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, Rehabilitation Centres, Special Schools',
    },
    {
        'career_name': 'Veterinary Doctor',
        'keywords': 'veterinary,veterinarian,vet,animal health,livestock',
        'salary_min': 80_000, 'salary_max': 250_000,
        'demand': 'Medium',
        'top_sectors': 'Livestock & Agriculture, NGOs, Wildlife, Food Safety',
    },
    {
        'career_name': 'Health Records Officer',
        'keywords': 'health records,health information,medical records,hrio',
        'salary_min': 35_000, 'salary_max': 80_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, County Government, Insurance',
    },

    # ── Engineering & Technology ─────────────────────────────────────────────
    {
        'career_name': 'Software Developer',
        'keywords': 'software developer,software engineer,programmer,web developer,mobile developer,backend,frontend,full stack,application developer',
        'salary_min': 60_000, 'salary_max': 300_000,
        'demand': 'High',
        'top_sectors': 'Tech Startups, Telecoms, Finance, E-Commerce, Consultancy',
    },
    {
        'career_name': 'Data Scientist',
        'keywords': 'data scientist,data analyst,machine learning,ai engineer,data engineer,business intelligence,bi analyst',
        'salary_min': 100_000, 'salary_max': 400_000,
        'demand': 'High',
        'top_sectors': 'Finance, Telecoms, Research Institutions, UN Agencies',
    },
    {
        'career_name': 'Network Engineer',
        'keywords': 'network engineer,network administrator,systems administrator,cybersecurity,it security,network technician,cisco,cloud engineer',
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
        'keywords': 'civil engineer,civil engineering,structural engineer,roads engineer,highways,infrastructure,drainage,geotechnical',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'High',
        'top_sectors': 'KeNHA, County Government, Construction Firms, Consultancies',
    },
    {
        'career_name': 'Building Technician',
        'keywords': 'building technician,building technology,construction technician,site supervisor,clerk of works',
        'salary_min': 35_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'Construction, Real Estate, County Government',
    },
    {
        'career_name': 'Electrical Engineer',
        'keywords': 'electrical engineer,power engineer,energy engineer,electrical & electronics',
        'salary_min': 75_000, 'salary_max': 280_000,
        'demand': 'High',
        'top_sectors': 'Kenya Power, KETRACO, Manufacturing, Telecoms',
    },
    {
        'career_name': 'Electrical Technician',
        'keywords': 'electrical technician,electrician,electrical installation,electrical wiring,power technician',
        'salary_min': 30_000, 'salary_max': 80_000,
        'demand': 'High',
        'top_sectors': 'Manufacturing, Construction, Utilities, Hotels',
    },
    {
        'career_name': 'Electronics Technician',
        'keywords': 'electronics technician,electronics,consumer electronics,appliance repair,instrumentation',
        'salary_min': 28_000, 'salary_max': 75_000,
        'demand': 'Medium',
        'top_sectors': 'Manufacturing, Repair Services, Broadcast Media',
    },
    {
        'career_name': 'Mechanical Engineer',
        'keywords': 'mechanical engineer,manufacturing engineer,production engineer,mechanical engineering',
        'salary_min': 70_000, 'salary_max': 250_000,
        'demand': 'High',
        'top_sectors': 'Manufacturing, Oil & Gas, Automotive, Construction',
    },
    {
        'career_name': 'Automotive Technician',
        'keywords': 'automotive technician,motor vehicle technician,mechanic,auto electrician,panel beater,automotive mechanic,motor vehicle mechanics',
        'salary_min': 25_000, 'salary_max': 70_000,
        'demand': 'High',
        'top_sectors': 'Vehicle Dealerships, Garages, Public Transport, Fleet Companies',
    },
    {
        'career_name': 'Chemical Engineer',
        'keywords': 'chemical engineer,chemical engineering,process engineer,petrochemical',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'Medium',
        'top_sectors': 'Manufacturing, Oil & Gas, FMCG, Water Treatment',
    },
    {
        'career_name': 'Quantity Surveyor',
        'keywords': 'quantity surveyor,qs,cost estimator,bills of quantities,construction cost',
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
        'keywords': 'land surveyor,survey,geomatics,cartography,gis,geospatial,geographic information',
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
        'keywords': 'welder,fabricator,welding,metal fabrication,boilermaker,structural steel',
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
        'keywords': 'accountant,accounting,cpa,financial accounting,management accounting,bookkeeper,accounts',
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
        'keywords': 'financial analyst,investment analyst,credit analyst,risk analyst,treasury,financial planning',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'High',
        'top_sectors': 'Commercial Banks, Investment Firms, NSE, Insurance',
    },
    {
        'career_name': 'Actuary',
        'keywords': 'actuary,actuarial,actuarial science,risk,insurance mathematics',
        'salary_min': 150_000, 'salary_max': 500_000,
        'demand': 'High',
        'top_sectors': 'Insurance, Pension Funds, Reinsurance, Consultancy',
    },
    {
        'career_name': 'Economist',
        'keywords': 'economist,economics,policy analyst,economic policy,macroeconomics,microeconomics,development economics',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'Medium',
        'top_sectors': 'Government, Central Bank, World Bank, NGOs, Research',
    },
    {
        'career_name': 'Lawyer / Advocate',
        'keywords': 'lawyer,advocate,barrister,solicitor,legal,law,llb,litigation,conveyancing,corporate law',
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
        'keywords': 'human resources,hr,human resource management,personnel,recruitment,talent management,hrm',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'High',
        'top_sectors': 'All Sectors — universal demand across industries',
    },
    {
        'career_name': 'Marketing Manager',
        'keywords': 'marketing,brand manager,digital marketing,sales,marketing officer,communications,advertising',
        'salary_min': 60_000, 'salary_max': 300_000,
        'demand': 'High',
        'top_sectors': 'FMCG, Telecoms, Banking, Retail, Agencies',
    },
    {
        'career_name': 'Supply Chain Officer',
        'keywords': 'supply chain,logistics,procurement,purchasing,inventory,warehouse,distribution,stores',
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
        'keywords': 'secondary teacher,high school teacher,tsc teacher,secondary education,form teacher',
        'salary_min': 30_000, 'salary_max': 80_000,
        'demand': 'High',
        'top_sectors': 'Public Schools (TSC), Private Schools, International Schools',
    },
    {
        'career_name': 'Primary School Teacher',
        'keywords': 'primary teacher,primary school,p1 teacher,upper primary,lower primary',
        'salary_min': 25_000, 'salary_max': 60_000,
        'demand': 'High',
        'top_sectors': 'Public Schools (TSC), Private Schools, Community Schools',
    },
    {
        'career_name': 'ECD Teacher',
        'keywords': 'ecd teacher,early childhood,nursery teacher,pre-school,kindergarten,pp1,pp2',
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
        'keywords': 'social worker,social work,community development,community organiser,welfare officer,probation',
        'salary_min': 35_000, 'salary_max': 90_000,
        'demand': 'Medium',
        'top_sectors': 'NGOs, County Government, Hospitals, Prison Service',
    },
    {
        'career_name': 'Psychologist / Counsellor',
        'keywords': 'psychologist,counsellor,counselor,psychology,mental health,guidance counsellor,therapist',
        'salary_min': 60_000, 'salary_max': 200_000,
        'demand': 'Medium',
        'top_sectors': 'Hospitals, NGOs, Schools, Corporates, Private Practice',
    },
    {
        'career_name': 'Librarian',
        'keywords': 'librarian,library,information science,records management,archives,archivist',
        'salary_min': 35_000, 'salary_max': 90_000,
        'demand': 'Low',
        'top_sectors': 'Universities, Schools, Government Ministries, Kenya National Archives',
    },

    # ── Agriculture & Environment ────────────────────────────────────────────
    {
        'career_name': 'Agronomist',
        'keywords': 'agronomist,agronomy,crop scientist,crop production,agri,soil scientist,crop extension',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Agriculture Companies, NGOs, KARI, Export Horticulture',
    },
    {
        'career_name': 'Agricultural Extension Officer',
        'keywords': 'agricultural extension,extension officer,agricultural officer,farm extension,aeo',
        'salary_min': 40_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'County Government, NGOs, Input Companies, Cooperatives',
    },
    {
        'career_name': 'Food Scientist',
        'keywords': 'food scientist,food technology,food quality,food processing,food safety,food production',
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
        'keywords': 'environmental scientist,environmental management,environmental impact,nema,waste management,ecology',
        'salary_min': 60_000, 'salary_max': 180_000,
        'demand': 'Medium',
        'top_sectors': 'NEMA, NGOs, Mining, Energy, Consultancy',
    },
    {
        'career_name': 'Forestry Officer',
        'keywords': 'forestry officer,forester,forest,kfs,afforestation,tree planting',
        'salary_min': 45_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'Kenya Forest Service, County Government, NGOs, Carbon Credits',
    },
    {
        'career_name': 'Fisheries Officer',
        'keywords': 'fisheries officer,fisheries,aquaculture,fish farming,marine science',
        'salary_min': 40_000, 'salary_max': 100_000,
        'demand': 'Low',
        'top_sectors': 'Government, Aquaculture Farms, NGOs, Lake Victoria Fisheries',
    },
    {
        'career_name': 'Animal Production Officer',
        'keywords': 'animal production,livestock,animal science,zootechnician,animal husbandry,dairy',
        'salary_min': 40_000, 'salary_max': 100_000,
        'demand': 'Medium',
        'top_sectors': 'County Government, Dairy Companies, Livestock NGOs, Ranches',
    },

    # ── Hospitality & Tourism ────────────────────────────────────────────────
    {
        'career_name': 'Hotel Manager',
        'keywords': 'hotel manager,hospitality management,hotel management,lodge manager,resort manager,food and beverage manager',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'Medium',
        'top_sectors': 'Hotels, Safari Lodges, Beach Resorts, Restaurant Chains',
    },
    {
        'career_name': 'Chef',
        'keywords': 'chef,cook,culinary,pastry chef,catering,food preparation,sous chef',
        'salary_min': 35_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'Hotels, Restaurants, Airlines, Offshore Catering, Events',
    },
    {
        'career_name': 'Catering Technician',
        'keywords': 'catering technician,food and beverage,catering,waitstaff,banqueting,hospitality operations',
        'salary_min': 22_000, 'salary_max': 60_000,
        'demand': 'Medium',
        'top_sectors': 'Hotels, Institutions, Outdoor Catering, Hospitals',
    },
    {
        'career_name': 'Tour Guide / Tourism Officer',
        'keywords': 'tour guide,tourism officer,tourist guide,safari guide,travel,ecotourism,park ranger',
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
        'keywords': 'event manager,events organiser,conference organiser,mice,wedding planner,event coordinator',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Event Companies, Hotels, NGOs, Corporates, Government',
    },

    # ── Creative, Design & Media ─────────────────────────────────────────────
    {
        'career_name': 'Graphic Designer',
        'keywords': 'graphic designer,graphic design,visual designer,ui designer,ux designer,brand designer,typographer',
        'salary_min': 40_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Advertising Agencies, Media Houses, Tech Companies, Freelance',
    },
    {
        'career_name': 'Journalist',
        'keywords': 'journalist,reporter,news,media,broadcast,photojournalist,editor,sub-editor',
        'salary_min': 35_000, 'salary_max': 120_000,
        'demand': 'Medium',
        'top_sectors': 'TV Stations, Newspapers, Online Media, NGOs',
    },
    {
        'career_name': 'Public Relations Officer',
        'keywords': 'public relations,pr officer,communications officer,corporate affairs,media relations,spokesperson',
        'salary_min': 50_000, 'salary_max': 150_000,
        'demand': 'Medium',
        'top_sectors': 'Corporates, Government, NGOs, PR Agencies',
    },
    {
        'career_name': 'Film & TV Producer',
        'keywords': 'filmmaker,film producer,video producer,videographer,cinematographer,director,media production,broadcast production',
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
        'keywords': 'fashion designer,fashion design,clothing design,textile,garment design,costume',
        'salary_min': 30_000, 'salary_max': 100_000,
        'demand': 'Low',
        'top_sectors': 'Fashion Houses, Export Industry, Entertainment, Retail',
    },

    # ── Trades & Artisan (TVET) ──────────────────────────────────────────────
    {
        'career_name': 'Hairdresser / Cosmetologist',
        'keywords': 'hairdresser,cosmetologist,beautician,hair stylist,barber,cosmetology,beauty therapy,nail technician',
        'salary_min': 20_000, 'salary_max': 60_000,
        'demand': 'Medium',
        'top_sectors': 'Salons, Hotels, Spas, Freelance, TV Production',
    },
    {
        'career_name': 'Tailor / Garment Maker',
        'keywords': 'tailor,garment,sewing,dressmaker,knitting,textile,clothing production,fashion artisan',
        'salary_min': 20_000, 'salary_max': 60_000,
        'demand': 'Medium',
        'top_sectors': 'Garment Factories, Export, Fashion, Freelance',
    },
    {
        'career_name': 'Carpenter / Joiner',
        'keywords': 'carpenter,joinery,cabinet maker,furniture maker,woodwork,wood technology',
        'salary_min': 25_000, 'salary_max': 70_000,
        'demand': 'Medium',
        'top_sectors': 'Furniture Industry, Construction, Real Estate',
    },
    {
        'career_name': 'Mason / Builder',
        'keywords': 'mason,masonry,bricklayer,builder,concrete,building construction,artisan builder',
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
        'keywords': 'marine engineer,maritime,shipping,naval,offshore,port management,marine transportation',
        'salary_min': 100_000, 'salary_max': 400_000,
        'demand': 'Medium',
        'top_sectors': 'Shipping Companies, KPA, Kenya Navy, Oil & Gas',
    },
    {
        'career_name': 'Geologist',
        'keywords': 'geologist,geology,mining engineer,minerals,petroleum geologist,hydrogeologist',
        'salary_min': 80_000, 'salary_max': 300_000,
        'demand': 'Medium',
        'top_sectors': 'Mining, Oil & Gas, NEMA, Water Resources, Consultancy',
    },
    {
        'career_name': 'Meteorologist',
        'keywords': 'meteorologist,weather,climate scientist,climatologist,atmospheric science',
        'salary_min': 60_000, 'salary_max': 200_000,
        'demand': 'Low',
        'top_sectors': 'Kenya Meteorological Dept, ICPAC, Aviation, Research',
    },
    {
        'career_name': 'Statistician',
        'keywords': 'statistician,statistics,biostatistics,quantitative analyst,data collection',
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
