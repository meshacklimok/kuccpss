"""
Seed the AIKnowledgeEntry table with verified Kenyan career guidance Q&A.
Run: python manage.py seed_knowledge
     python manage.py seed_knowledge --clear   (wipe first)
"""
from django.core.management.base import BaseCommand
from career.models import AIKnowledgeEntry

ENTRIES = [

    # ═══════════════════════════════════════════════
    # PATHWAYS — grade rules, what each pathway means
    # ═══════════════════════════════════════════════
    {
        "category": "pathway",
        "question": "What KCSE grade do I need to study a degree in Kenya?",
        "answer": (
            "To qualify for a university degree in Kenya you need a minimum mean grade of C+. "
            "KUCCPS ranks degree applicants using cluster points (0–48), which are calculated from "
            "your grades in four specific cluster subjects for each course. The higher your cluster "
            "points, the more competitive courses you can access. You submit up to 6 course choices for degree."
        ),
        "keywords": "degree,c+,university,cluster points,kuccps,qualify,grade,minimum",
        "order": 1,
    },
    {
        "category": "pathway",
        "question": "What grade do I need for a diploma in Kenya?",
        "answer": (
            "Most diploma programmes in Kenya require a minimum mean grade of C (plain). "
            "Some diploma courses accept C- depending on the institution and subject combination. "
            "Diplomas are offered at universities, national polytechnics, and technical institutes. "
            "For non-degree KUCCPS placement (diploma, KMTC, TVET, TTC) you submit only 2 course choices."
        ),
        "keywords": "diploma,c,c-,grade,polytechnic,minimum,qualify,kuccps",
        "order": 2,
    },
    {
        "category": "pathway",
        "question": "What grade do I need for a certificate course in Kenya?",
        "answer": (
            "Certificate courses in Kenya generally require a minimum mean grade of C- (C minus). "
            "Some specific certificate programmes accept D+ depending on the course and institution. "
            "Certificate programmes run 1–2 years and are offered at TVETs and polytechnics. "
            "For non-degree KUCCPS placement you submit only 2 course choices."
        ),
        "keywords": "certificate,c-,d+,grade,tvet,polytechnic,minimum,qualify",
        "order": 3,
    },
    {
        "category": "pathway",
        "question": "What can I study if I got below D+ in KCSE (D, D-, E)?",
        "answer": (
            "If your KCSE mean grade is D or below you can pursue artisan and craft certificate programmes "
            "at TVETs and technical institutes across Kenya. Artisan courses cover trades like plumbing, "
            "masonry, carpentry, electrical installation, motor vehicle mechanics, and welding. "
            "These are practical, hands-on programmes that lead directly to employment or self-employment. "
            "Duration is typically 1 year or less."
        ),
        "keywords": "artisan,d,d-,e,craft,tvet,below d+,low grade,trade",
        "order": 4,
    },
    {
        "category": "pathway",
        "question": "What is the difference between Degree, Diploma, Certificate, and Artisan in Kenya?",
        "answer": (
            "Degree: 4 years at university, minimum grade C+, cluster points used for ranking.\n"
            "Diploma: 2–3 years at university or polytechnic, minimum grade C or C-.\n"
            "Certificate: 1–2 years at TVET/polytechnic, minimum grade C- or D+.\n"
            "Artisan/Craft: Less than 1 year at TVET, for students with grade D and below.\n"
            "Non-degree applicants (diploma, KMTC, TVET, TTC) submit only 2 KUCCPS choices."
        ),
        "keywords": "degree,diploma,certificate,artisan,difference,grade,comparison,pathway",
        "order": 5,
    },
    {
        "category": "pathway",
        "question": "What is KMTC and what grade do I need?",
        "answer": (
            "KMTC (Kenya Medical Training College) is a government institution that offers medical and "
            "paramedical diploma courses including Nursing, Clinical Medicine, Pharmacy, Medical Lab Technology, "
            "Health Records, Nutrition, and many more. Most KMTC courses require a minimum mean grade of C. "
            "Some competitive courses like Clinical Medicine and Nursing may require C+ and specific subject passes "
            "in Biology, Chemistry, or Physics. KMTC applicants submit 2 choices via KUCCPS."
        ),
        "keywords": "kmtc,kenya medical training college,nursing,clinical medicine,pharmacy,c,grade,medical",
        "order": 6,
    },
    {
        "category": "pathway",
        "question": "What is a TTC and what grade do I need?",
        "answer": (
            "TTC (Teachers Training College) trains primary school teachers. The main programme is the "
            "Primary Teacher Education (P1 certificate). It requires a minimum mean grade of C or C- "
            "depending on the college. After completing P1 you can teach in public primary schools in Kenya. "
            "TTC applicants submit 2 choices via KUCCPS."
        ),
        "keywords": "ttc,teachers training college,p1,primary teacher,education,c,c-,grade",
        "order": 7,
    },
    {
        "category": "pathway",
        "question": "What is a TVET in Kenya?",
        "answer": (
            "TVET (Technical and Vocational Education and Training) refers to polytechnics and technical "
            "institutes that offer practical training in trades and technical fields. Levels include: "
            "Artisan (grade D and below), Certificate (D+ to C-), Diploma (C to C+). "
            "Popular TVET fields: Engineering Technology, ICT, Business, Hospitality, Construction, "
            "Agriculture, Fashion and Design, Health Sciences. "
            "TVET applicants submit 2 choices via KUCCPS."
        ),
        "keywords": "tvet,polytechnic,technical,vocational,artisan,certificate,diploma,trade",
        "order": 8,
    },
    {
        "category": "pathway",
        "question": "How many KUCCPS choices do I get for non-degree courses?",
        "answer": (
            "For non-degree pathways (Diploma, KMTC, TVET Certificate, TTC, Artisan) KUCCPS allows "
            "you to submit only 2 course choices. Rank them in order of preference. "
            "For degree programmes you can submit up to 6 choices. "
            "Always apply for your most preferred course first."
        ),
        "keywords": "kuccps,choices,non-degree,diploma,kmtc,tvet,ttc,artisan,2 choices,how many",
        "order": 9,
    },

    # ═══════════════════════════════════════════════
    # GRADE → CAREER
    # ═══════════════════════════════════════════════
    {
        "category": "grade_career",
        "question": "I got C+ in KCSE, what courses can I study in Kenya?",
        "answer": (
            "With C+ you qualify for degree programmes at Kenyan universities. Good options include: "
            "Education (Arts or Science), Business Administration, IT/Computer Studies, Journalism, "
            "Social Work, Agriculture, Environmental Science, and many more. "
            "Your specific cluster points for each course determine which degree you can access. "
            "You also qualify for all diploma, certificate, and KMTC courses."
        ),
        "keywords": "c+,courses,degree,qualify,study,options,university",
        "order": 1,
    },
    {
        "category": "grade_career",
        "question": "I got C in KCSE, what can I study?",
        "answer": (
            "With a mean grade of C you qualify for diploma programmes, KMTC courses, TTC (P1 teacher), "
            "and TVET diploma programmes. You do NOT qualify for university degree placement via KUCCPS. "
            "Good diploma options: Business Management, IT, Nursing (KMTC), Clinical Medicine (KMTC), "
            "Electrical Engineering (TVET), Hospitality Management. "
            "Work hard in your chosen diploma — you can later upgrade to a degree through bridging programmes."
        ),
        "keywords": "c,plain c,grade,diploma,kmtc,tvet,courses,qualify,options",
        "order": 2,
    },
    {
        "category": "grade_career",
        "question": "I got C- in KCSE, what can I study?",
        "answer": (
            "With C- you can qualify for: some diploma courses (check specific requirements), "
            "TVET certificate programmes, TTC teacher training (some colleges), and most artisan courses. "
            "KMTC is generally not accessible at C-. "
            "Recommended paths: TVET Certificate in ICT, Electrical, Business, or Hospitality. "
            "You can upgrade through the TVET system as your skills grow."
        ),
        "keywords": "c-,c minus,grade,certificate,tvet,artisan,courses,qualify,options",
        "order": 3,
    },
    {
        "category": "grade_career",
        "question": "I got D+ in KCSE, what options do I have?",
        "answer": (
            "D+ qualifies you for certificate-level programmes at TVETs. "
            "Options include: Certificate in Electrical Installation, Motor Vehicle Mechanics, "
            "Plumbing, ICT, Business, Food Production, and Construction. "
            "Duration is 1–2 years. You can then upgrade to diploma level. "
            "Some private colleges also offer bridging courses to help you meet higher entry requirements."
        ),
        "keywords": "d+,grade,certificate,tvet,courses,qualify,options,artisan",
        "order": 4,
    },
    {
        "category": "grade_career",
        "question": "What can a student with grade B or above study in Kenya?",
        "answer": (
            "With B and above you have excellent options for competitive degree programmes: "
            "Medicine, Pharmacy, Engineering, Law, Architecture, Computer Science, Actuarial Science, "
            "and other high-demand courses at top universities like UoN, KU, and JKUAT. "
            "Your cluster points will be high, giving you access to courses with high cutoffs."
        ),
        "keywords": "b,b+,a,a-,grade,competitive,medicine,engineering,law,university,degree",
        "order": 5,
    },
    {
        "category": "grade_career",
        "question": "What careers are available for someone who scored D and below in KCSE?",
        "answer": (
            "With D or below you can pursue artisan and craft trades at TVETs: "
            "Plumber, Electrician, Mason, Carpenter, Welder, Motor Vehicle Mechanic, Tailor/Fashion Designer. "
            "These are skilled trades with real job demand in Kenya. Many artisans become self-employed "
            "and earn very well. You can later upgrade through the TVET system to certificate and diploma level."
        ),
        "keywords": "d,d-,e,artisan,trade,craft,tvet,career,electrician,plumber,mechanic,options",
        "order": 6,
    },

    # ═══════════════════════════════════════════════
    # INTEREST → CAREER
    # ═══════════════════════════════════════════════
    {
        "category": "interest_career",
        "question": "I like mathematics and computers, what careers suit me?",
        "answer": (
            "Strong careers for math and computer lovers in Kenya: Software Engineer, Data Scientist, "
            "Cybersecurity Analyst, Actuary, Systems Analyst, Network Engineer, ICT Manager, "
            "Statistician, and Financial Analyst. "
            "Recommended degree courses: Computer Science, Software Engineering, Actuarial Science, "
            "Statistics, Information Technology. Minimum grade C+ for degree."
        ),
        "keywords": "mathematics,math,computers,ict,technology,software,engineering,interest,career",
        "order": 1,
    },
    {
        "category": "interest_career",
        "question": "I enjoy biology and helping people, what careers fit me?",
        "answer": (
            "If you love biology and caring for people, consider: Medicine (MBChB), Nursing, "
            "Clinical Medicine (KMTC), Pharmacy, Medical Lab Technology, Nutrition and Dietetics, "
            "Physiotherapy, Public Health, Biomedical Science, or Veterinary Medicine. "
            "Medicine requires very high cluster points (usually 40+). Nursing via KMTC requires C. "
            "These careers are in high demand in Kenya and across Africa."
        ),
        "keywords": "biology,helping,medicine,nursing,clinical,pharmacy,health,interest,career",
        "order": 2,
    },
    {
        "category": "interest_career",
        "question": "I am interested in business and leadership, what should I study?",
        "answer": (
            "Great business careers in Kenya: Business Manager, Entrepreneur, Accountant, Banker, "
            "Marketing Manager, Supply Chain Manager, Human Resource Manager, Economist. "
            "Recommended courses: Business Administration, Commerce, Economics, Accounting, "
            "Finance, Procurement and Supply Chain Management, Human Resource Management. "
            "Available at both degree level (C+) and diploma level (C)."
        ),
        "keywords": "business,leadership,management,accounting,economics,finance,entrepreneur,interest",
        "order": 3,
    },
    {
        "category": "interest_career",
        "question": "I like technology and creativity, what careers match me?",
        "answer": (
            "Technology + creativity opens exciting paths: UI/UX Designer, Graphic Designer, "
            "Architect, Multimedia Producer, Game Developer, Film/Animation Producer, "
            "Industrial Designer, Interior Designer, Web Designer. "
            "Courses: Architecture, Fine Art and Design, ICT, Film and Animation, "
            "Media and Communication. Grade C+ for degree, C for diploma."
        ),
        "keywords": "technology,creativity,design,art,media,animation,architecture,interest,career",
        "order": 4,
    },
    {
        "category": "interest_career",
        "question": "I enjoy teaching and working with children, what career should I pursue?",
        "answer": (
            "If you love teaching and working with children, consider: "
            "Primary Teacher (P1 via TTC, grade C or C-), Secondary Teacher (Education degree, grade C+), "
            "Early Childhood Development (ECD), Social Work, or Psychology. "
            "TSC (Teachers Service Commission) employs trained teachers in government schools. "
            "Private schools also hire qualified teachers."
        ),
        "keywords": "teaching,teacher,children,education,ttc,p1,interest,career,school",
        "order": 5,
    },
    {
        "category": "interest_career",
        "question": "I like agriculture and the environment, what careers are available?",
        "answer": (
            "Agriculture and environment careers in Kenya: Agricultural Officer, Agronomist, "
            "Soil Scientist, Environmental Manager, Wildlife Officer, Forester, Food Technologist, "
            "Horticulturist. Kenya's agricultural sector is large and growing. "
            "Courses: Agriculture, Environmental Science, Food Science, Natural Resource Management, "
            "Horticulture. Available at degree (C+) and diploma (C) level."
        ),
        "keywords": "agriculture,environment,farming,food,wildlife,agronomist,interest,career",
        "order": 6,
    },

    # ═══════════════════════════════════════════════
    # COURSE EXPLANATIONS
    # ═══════════════════════════════════════════════
    {
        "category": "course_info",
        "question": "What is Computer Science and what do you study?",
        "answer": (
            "Computer Science is a 4-year degree that covers programming, algorithms, data structures, "
            "artificial intelligence, databases, networking, and software development. "
            "It requires C+ minimum and strong Mathematics and Physics. "
            "Offered at UoN, JKUAT, Strathmore, KU, Moi University, and many others. "
            "Graduates work as software engineers, data scientists, system analysts, and AI specialists."
        ),
        "keywords": "computer science,programming,software,degree,what is,study,course",
        "order": 1,
    },
    {
        "category": "course_info",
        "question": "What is Medicine (MBChB) and how long does it take?",
        "answer": (
            "Medicine (MBChB) is a 6-year degree that trains medical doctors. You study Anatomy, "
            "Physiology, Pharmacology, Pathology, Surgery, and Clinical Medicine. "
            "It requires very high cluster points (usually 40+ out of 48) and strong Biology, Chemistry, Physics. "
            "Offered at UoN, UoE, Moi, Maseno, JOOUST. Graduates become doctors — "
            "the most respected profession in Kenya. Salary ranges from KSh 150,000–500,000+/month."
        ),
        "keywords": "medicine,mbchb,doctor,medical school,how long,6 years,study,course",
        "order": 2,
    },
    {
        "category": "course_info",
        "question": "What is Engineering and what are the types?",
        "answer": (
            "Engineering trains you to design, build, and maintain systems and structures. "
            "Main types in Kenya: Civil Engineering (roads, bridges), Electrical Engineering (power), "
            "Mechanical Engineering (machines), Computer Engineering (hardware/software), "
            "Chemical Engineering (industrial processes), Aerospace Engineering. "
            "Duration: 4–5 years. Minimum grade C+. Strong Mathematics and Physics required. "
            "Offered at JKUAT, UoN, Moi, TUK, Dedan Kimathi University."
        ),
        "keywords": "engineering,civil,electrical,mechanical,what is,degree,study,course,types",
        "order": 3,
    },
    {
        "category": "course_info",
        "question": "What is Nursing and how long does it take in Kenya?",
        "answer": (
            "Nursing trains you to care for patients in hospitals and clinics. "
            "KMTC Nursing diploma: 3 years, requires minimum grade C, plus Biology and Chemistry. "
            "Degree in Nursing (BScN): 4 years at university, requires C+ minimum. "
            "Nurses work in government hospitals, private hospitals, NGOs, and abroad. "
            "Salary: KSh 30,000–100,000/month depending on experience and sector."
        ),
        "keywords": "nursing,nurse,kmtc,diploma,degree,how long,study,course",
        "order": 4,
    },
    {
        "category": "course_info",
        "question": "What is Business Administration and what jobs can I get?",
        "answer": (
            "Business Administration covers management, finance, marketing, human resources, and strategy. "
            "Duration: 4 years (degree), 2 years (diploma). Minimum grade C+ (degree) or C (diploma). "
            "Jobs: Business Manager, HR Manager, Marketing Executive, Operations Manager, Entrepreneur. "
            "It is one of the most versatile degrees — graduates work in almost every sector."
        ),
        "keywords": "business administration,management,marketing,hr,jobs,course,what is",
        "order": 5,
    },
    {
        "category": "course_info",
        "question": "What is Clinical Medicine (KMTC) and how long is it?",
        "answer": (
            "Clinical Medicine is a 3-year KMTC diploma that trains Clinical Officers — "
            "who are like doctors in rural and underserved areas. They diagnose, prescribe, and treat. "
            "Minimum grade C, with Biology and Chemistry. Very competitive — cutoffs are high at popular campuses. "
            "Salary starts at KSh 40,000–80,000/month in government service. High demand especially in rural Kenya."
        ),
        "keywords": "clinical medicine,clinical officer,kmtc,diploma,how long,study,course",
        "order": 6,
    },
    {
        "category": "course_info",
        "question": "What is the difference between Software Engineering and Computer Science?",
        "answer": (
            "Computer Science focuses more on theory — algorithms, AI, data structures, mathematics. "
            "Software Engineering focuses more on practice — building large software systems, "
            "project management, testing, and design patterns. "
            "In Kenya both lead to similar jobs and both require C+ minimum with strong Mathematics. "
            "Both are excellent choices for the tech industry."
        ),
        "keywords": "software engineering,computer science,difference,comparison,ict,degree",
        "order": 7,
    },
    {
        "category": "course_info",
        "question": "What is Actuarial Science and is it good in Kenya?",
        "answer": (
            "Actuarial Science uses advanced mathematics and statistics to assess risk for insurance companies, "
            "banks, and investment firms. It is one of the most competitive and well-paying degrees in Kenya. "
            "Minimum grade: A- or A with very strong Mathematics. Offered at UoN, Maseno, KU, Strathmore. "
            "Actuaries earn KSh 150,000–400,000+/month and are in demand globally."
        ),
        "keywords": "actuarial science,mathematics,statistics,insurance,risk,degree,salary",
        "order": 8,
    },
    {
        "category": "course_info",
        "question": "What is Law (LLB) in Kenya and what does it involve?",
        "answer": (
            "LLB (Bachelor of Laws) is a 4-year degree that covers Constitutional Law, Contract Law, "
            "Criminal Law, Civil Procedure, Commercial Law, and International Law. "
            "After graduation you do the Advocates Training Programme (ATP) at KSL to become an advocate. "
            "Minimum grade: usually B+ or A at UoN School of Law (very competitive cluster points needed). "
            "Lawyers work in firms, government, NGOs, or as independent advocates."
        ),
        "keywords": "law,llb,lawyer,advocate,ksl,what is,degree,course",
        "order": 9,
    },

    # ═══════════════════════════════════════════════
    # CAREER OUTCOMES & SALARY
    # ═══════════════════════════════════════════════
    {
        "category": "career_outcome",
        "question": "How much does a software engineer earn in Kenya?",
        "answer": (
            "Software engineers are among the highest-paid professionals in Kenya. "
            "Entry level (0–2 years): KSh 60,000–120,000/month. "
            "Mid-level (3–5 years): KSh 150,000–300,000/month. "
            "Senior (5+ years): KSh 300,000–600,000+/month. "
            "Remote work for international companies can pay even more in USD. "
            "Demand is very high — Kenya has a growing tech hub in Nairobi (Silicon Savannah)."
        ),
        "keywords": "software engineer,salary,earn,income,pay,tech,programming,kenya",
        "order": 1,
    },
    {
        "category": "career_outcome",
        "question": "How much does a doctor (medical officer) earn in Kenya?",
        "answer": (
            "Government doctors (Medical Officers) in Kenya start at approximately KSh 150,000–200,000/month. "
            "Specialists (surgeons, physicians, gynaecologists) earn KSh 300,000–700,000+/month. "
            "Private practice doctors can earn significantly more. "
            "Medicine is a long investment (6 years + internship) but offers job security, respect, and high income."
        ),
        "keywords": "doctor,medical officer,salary,earn,income,pay,medicine,kenya",
        "order": 2,
    },
    {
        "category": "career_outcome",
        "question": "How much does a nurse earn in Kenya?",
        "answer": (
            "Government nurses in Kenya earn approximately KSh 30,000–80,000/month depending on grade. "
            "Private hospitals pay KSh 50,000–120,000/month. "
            "Nurses who go abroad (UK, Saudi Arabia, Canada) can earn KSh 250,000–500,000+ equivalent/month. "
            "Nursing is in very high international demand — many Kenyan nurses work overseas."
        ),
        "keywords": "nurse,nursing,salary,earn,income,pay,kenya,kmtc",
        "order": 3,
    },
    {
        "category": "career_outcome",
        "question": "How much does a civil engineer earn in Kenya?",
        "answer": (
            "Civil engineers in Kenya earn KSh 80,000–150,000/month at entry level. "
            "With 5+ years experience: KSh 200,000–400,000+/month. "
            "Government engineers earn slightly less but have job security and pension. "
            "Construction is booming in Kenya — roads, buildings, dams — so demand is high."
        ),
        "keywords": "civil engineer,engineer,salary,earn,income,pay,construction,kenya",
        "order": 4,
    },
    {
        "category": "career_outcome",
        "question": "Which careers are well-paying in Kenya?",
        "answer": (
            "Top-paying careers in Kenya (approximate monthly earnings):\n"
            "• Medicine/Specialists: KSh 200,000–700,000\n"
            "• Actuarial Science: KSh 150,000–400,000\n"
            "• Software Engineering: KSh 80,000–600,000\n"
            "• Law (Advocates): KSh 80,000–500,000\n"
            "• Architecture: KSh 80,000–300,000\n"
            "• Finance/Investment Banking: KSh 80,000–300,000\n"
            "• Aviation/Pilots: KSh 200,000–500,000\n"
            "High pay usually requires many years of study and experience."
        ),
        "keywords": "well-paying,high salary,earn,income,top careers,best paying,money,kenya",
        "order": 5,
    },
    {
        "category": "career_outcome",
        "question": "Is medicine worth it financially in Kenya?",
        "answer": (
            "Yes — medicine is one of the most financially rewarding careers in Kenya long-term. "
            "It takes 6 years of study plus 1 year internship (7 years total). "
            "Starting salary is ~KSh 150,000/month. Specialists earn KSh 300,000–700,000+/month. "
            "Private practice can exceed KSh 1 million/month for experienced specialists. "
            "It also offers extremely high job security — doctors are always needed."
        ),
        "keywords": "medicine,worth it,salary,financial,investment,doctor,income,kenya",
        "order": 6,
    },
    {
        "category": "career_outcome",
        "question": "What jobs can I get with an ICT or Computer Science degree?",
        "answer": (
            "With an ICT or Computer Science degree in Kenya you can work as: "
            "Software Developer, Web Developer, Mobile App Developer, Data Analyst, "
            "Cybersecurity Analyst, Network Administrator, IT Manager, Database Administrator, "
            "AI/Machine Learning Engineer, or start your own tech company. "
            "Kenyan tech sector is growing fast — M-Pesa, Andela, and Safaricom all hire locally."
        ),
        "keywords": "ict,computer science,jobs,career,software,developer,data,network,degree",
        "order": 7,
    },

    # ═══════════════════════════════════════════════
    # UNIVERSITY & ADMISSION
    # ═══════════════════════════════════════════════
    {
        "category": "admission",
        "question": "Which universities offer Computer Science in Kenya?",
        "answer": (
            "Computer Science is offered at many universities in Kenya including: "
            "University of Nairobi (UoN), JKUAT, Kenyatta University, Strathmore University, "
            "Moi University, Maseno University, Multimedia University, Kabarak University, "
            "Dedan Kimathi University of Technology, and many others. "
            "UoN and Strathmore are highly regarded for tech programmes."
        ),
        "keywords": "computer science,universities,which university,offer,kenya,uon,jkuat,strathmore",
        "order": 1,
    },
    {
        "category": "admission",
        "question": "Which university is best for Medicine in Kenya?",
        "answer": (
            "Top universities for Medicine (MBChB) in Kenya: "
            "University of Nairobi (UoN) — oldest and highly ranked. "
            "Moi University School of Medicine — strong clinical training. "
            "University of Eldoret (UoE) — newer but growing. "
            "Maseno University and JOOUST — also accredited. "
            "All require very high cluster points. Check current KUCCPS cutoffs as they vary each year."
        ),
        "keywords": "medicine,mbchb,best university,uon,moi,medical school,kenya,which university",
        "order": 2,
    },
    {
        "category": "admission",
        "question": "What is the difference between public and private university in Kenya?",
        "answer": (
            "Public universities (UoN, KU, JKUAT, Moi, Maseno): Lower fees for government-sponsored students, "
            "higher competition for placement, degrees widely recognised in Kenya. "
            "Private universities (Strathmore, USIU, Daystar, KCA, Kabarak): Higher fees, smaller classes, "
            "faster admission, some with international accreditation. "
            "For KUCCPS government-sponsored placement, only public universities are available. "
            "Private universities offer self-sponsored admission directly."
        ),
        "keywords": "public,private,university,difference,fees,comparison,kuccps,kenya",
        "order": 3,
    },
    {
        "category": "admission",
        "question": "What is KUCCPS and how does it work?",
        "answer": (
            "KUCCPS (Kenya Universities and Colleges Central Placement Service) is the government body "
            "that places KCSE candidates into universities, KMTCs, TVETs, and TTCs. "
            "After KNEC releases KCSE results, KUCCPS opens a portal where you submit your course choices. "
            "Degree applicants submit up to 6 choices; non-degree applicants submit 2 choices. "
            "KUCCPS ranks applicants by cluster points (degree) or mean grade (other pathways) and places "
            "each student in the highest-ranked course they qualify for."
        ),
        "keywords": "kuccps,what is,how works,placement,university,choices,application",
        "order": 4,
    },
    {
        "category": "admission",
        "question": "What happens if I don't get placed by KUCCPS?",
        "answer": (
            "If you are not placed in any of your choices, KUCCPS may: "
            "1. Place you in another course you qualify for (inter-institutional transfer). "
            "2. Open a revision of choices window where you can change your applications. "
            "You can also apply directly to universities as a self-sponsored student (pay your own fees). "
            "Some students also repeat KCSE or take bridging/foundation courses to improve their grade."
        ),
        "keywords": "not placed,kuccps,revision,choices,self-sponsored,repeat,bridging,what happens",
        "order": 5,
    },

    # ═══════════════════════════════════════════════
    # COMPARISONS
    # ═══════════════════════════════════════════════
    {
        "category": "comparison",
        "question": "Compare Medicine vs Pharmacy in Kenya",
        "answer": (
            "Medicine (MBChB): 6 years, trains doctors. Requires very high cluster points (40+). "
            "Salary: KSh 150,000–700,000+/month. Very competitive admission.\n"
            "Pharmacy (BPharm): 4–5 years, trains pharmacists who dispense medicines and advise patients. "
            "Requires B+ or above. Salary: KSh 80,000–200,000/month. "
            "Both are excellent but Medicine has higher demand, higher pay, and harder entry."
        ),
        "keywords": "medicine,pharmacy,compare,difference,vs,which better,doctor,pharmacist",
        "order": 1,
    },
    {
        "category": "comparison",
        "question": "Diploma vs Degree — which is better in Kenya?",
        "answer": (
            "Degree (4 years): Higher earning potential, opens management and professional roles, "
            "required for some licenced professions. Minimum grade C+. "
            "Diploma (2–3 years): Faster, cheaper, more practical, minimum grade C or C-. "
            "Many diploma holders earn well and outperform degree holders in practical fields. "
            "Best strategy: do a diploma if your grade doesn't qualify for degree, then upgrade later — "
            "many universities accept diploma holders into second-year degree programmes."
        ),
        "keywords": "diploma,degree,which better,difference,compare,upgrade,qualification,kenya",
        "order": 2,
    },
    {
        "category": "comparison",
        "question": "IT vs Computer Science — what is the difference?",
        "answer": (
            "Computer Science: More theoretical — algorithms, programming languages, AI, data structures. "
            "Ideal for deep technical work and research. "
            "Information Technology (IT): More practical — networks, systems administration, "
            "database management, user support, and business applications. "
            "In Kenya both lead to similar jobs. Computer Science graduates often earn slightly more "
            "in software development, while IT graduates thrive in corporate IT departments."
        ),
        "keywords": "it,information technology,computer science,difference,compare,ict,degree",
        "order": 3,
    },
    {
        "category": "comparison",
        "question": "Nursing vs Clinical Medicine — which is better in Kenya?",
        "answer": (
            "Clinical Medicine (Clinical Officer): Diagnoses and treats patients independently, prescribes medication. "
            "3 years KMTC. Salary KSh 40,000–100,000/month government. Very high responsibility.\n"
            "Nursing: Provides direct patient care, administers treatment. 3 years KMTC or 4-year degree. "
            "Salary KSh 30,000–80,000/month government. High international demand — many nurses go abroad.\n"
            "Both are excellent. Nursing has better international opportunities; Clinical Medicine has more autonomy locally."
        ),
        "keywords": "nursing,clinical medicine,compare,difference,which better,kmtc,nurse,clinical officer",
        "order": 4,
    },

    # ═══════════════════════════════════════════════
    # DECISION HELP
    # ═══════════════════════════════════════════════
    {
        "category": "decision",
        "question": "I don't know what to study after KCSE, how do I choose a career?",
        "answer": (
            "Here is a simple framework to choose your career:\n"
            "1. What subjects did you enjoy most in school? Those subjects point to your strengths.\n"
            "2. What problems do you like solving? (People problems → health/social work; "
            "technical problems → engineering/IT; number problems → finance/actuarial).\n"
            "3. What lifestyle do you want? (High income, outdoor work, creativity, stability?)\n"
            "4. What grade did you get? That determines your pathway.\n"
            "Combine these answers and explore courses that match. Take our career quiz above — "
            "it helps match your interests to real careers in Kenya."
        ),
        "keywords": "confused,don't know,choose,career,decision,help,what to study,kcse,guide",
        "order": 1,
    },
    {
        "category": "decision",
        "question": "What careers are safe and stable in Kenya?",
        "answer": (
            "Stable and secure careers in Kenya with consistent government/private demand:\n"
            "• Teaching (TSC employs thousands annually)\n"
            "• Nursing and Clinical Medicine (always needed)\n"
            "• Civil Engineering (infrastructure boom)\n"
            "• Accounting and Finance (every organisation needs accountants)\n"
            "• IT and Cybersecurity (growing fast)\n"
            "• Law (always in demand)\n"
            "• Agriculture (backbone of Kenyan economy)\n"
            "These fields have structured career paths and predictable income growth."
        ),
        "keywords": "safe,stable,career,secure,job security,demand,kenya,consistent",
        "order": 2,
    },
    {
        "category": "decision",
        "question": "What are the best courses with the highest job opportunities in Kenya?",
        "answer": (
            "Courses with the highest job opportunities in Kenya right now:\n"
            "• Software Engineering / Computer Science (tech boom)\n"
            "• Nursing (local + international demand)\n"
            "• Clinical Medicine (rural health gap)\n"
            "• Civil Engineering (SGR, roads, buildings)\n"
            "• Education (teacher shortage in rural areas)\n"
            "• Accounting and Finance (every sector)\n"
            "• Agriculture (food security priority)\n"
            "• Cybersecurity (rapidly growing field)"
        ),
        "keywords": "best courses,job opportunities,demand,highest,employment,career,kenya",
        "order": 3,
    },
    {
        "category": "decision",
        "question": "What should I do after KCSE if I am confused?",
        "answer": (
            "After KCSE, take these steps:\n"
            "1. Wait for your official KNEC results slip — don't rely on unofficial marks.\n"
            "2. Calculate your mean grade and cluster points (use this platform).\n"
            "3. Explore courses that match your grade and interests.\n"
            "4. Apply on KUCCPS portal when it opens (check kuccps.net).\n"
            "5. If your grade limits options, consider repeating KCSE or starting with a diploma "
            "and upgrading later.\n"
            "Don't rush — take time to research and choose something you will enjoy for years."
        ),
        "keywords": "after kcse,confused,next steps,what to do,kuccps,results,guidance",
        "order": 4,
    },

    # ═══════════════════════════════════════════════
    # FUTURE TRENDS
    # ═══════════════════════════════════════════════
    {
        "category": "future_trends",
        "question": "Which careers will be in demand in Kenya in 5–10 years?",
        "answer": (
            "High-demand careers in Kenya over the next 5–10 years:\n"
            "• Software Engineering and AI/ML Engineers (digital transformation)\n"
            "• Cybersecurity Specialists (rising cyber threats)\n"
            "• Data Scientists and Analysts (data-driven business)\n"
            "• Renewable Energy Engineers (solar, wind — Vision 2030)\n"
            "• Healthcare workers — Nurses, Doctors, Clinical Officers\n"
            "• Climate/Environmental Scientists (green economy)\n"
            "• Teachers and Education Technology specialists\n"
            "These fields align with Kenya's Vision 2030 and Big 4 Agenda priorities."
        ),
        "keywords": "future,demand,5 years,10 years,trends,careers,technology,kenya,vision 2030",
        "order": 1,
    },
    {
        "category": "future_trends",
        "question": "Is AI (Artificial Intelligence) a good career choice in Kenya?",
        "answer": (
            "Yes — AI is one of the fastest-growing career fields globally and in Kenya. "
            "AI Engineers, Machine Learning Engineers, and Data Scientists are in very high demand. "
            "Entry paths: Computer Science or Data Science degree, then specialise in AI/ML. "
            "Kenyan companies, banks, telecoms, and government agencies are adopting AI rapidly. "
            "Remote work opportunities for Kenyan AI engineers are abundant — you can work for global companies. "
            "Start building skills in Python, statistics, and machine learning early."
        ),
        "keywords": "ai,artificial intelligence,machine learning,career,future,kenya,data science",
        "order": 2,
    },
    {
        "category": "future_trends",
        "question": "Which courses are future-proof in Kenya?",
        "answer": (
            "Future-proof courses in Kenya (still relevant in 20+ years):\n"
            "• Medicine and Healthcare (humans always need doctors and nurses)\n"
            "• Engineering (infrastructure never stops)\n"
            "• Computer Science / AI (technology only grows)\n"
            "• Education (teachers remain essential)\n"
            "• Agriculture and Food Science (food security is permanent)\n"
            "• Renewable Energy (clean energy transition is inevitable)\n"
            "• Law (legal systems persist regardless of technology)\n"
            "Avoid courses with very narrow applications in fast-changing industries."
        ),
        "keywords": "future-proof,courses,future,long-term,career,safe choice,kenya",
        "order": 3,
    },
    {
        "category": "future_trends",
        "question": "Will technology replace some careers in Kenya?",
        "answer": (
            "Yes — automation and AI will reduce demand for some roles: "
            "routine data entry, basic accounting, simple customer service, and manual manufacturing. "
            "However, technology also creates new careers. Safe from automation: "
            "Doctors, Nurses, Teachers, Engineers, Creative Professionals, Lawyers, and Skilled Tradespeople. "
            "The key is to combine technical skills with human skills (communication, empathy, leadership) — "
            "these are hardest for machines to replace."
        ),
        "keywords": "technology,automation,ai,replace,jobs,future,career,Kenya,robots",
        "order": 4,
    },

    # ═══════════════════════════════════════════════
    # GENERAL
    # ═══════════════════════════════════════════════
    {
        "category": "general",
        "question": "What is KUCCPSS and how does it help students?",
        "answer": (
            "KUCCPSS is a free online platform that helps Kenyan KCSE students: "
            "1. Calculate their cluster points using the official KUCCPS formula. "
            "2. Discover which university courses, KMTC programmes, TVETs, and TTCs they qualify for. "
            "3. Get AI-powered career guidance tailored to their grade, subjects, and interests. "
            "It is not an official KUCCPS portal — students must apply on kuccps.net — "
            "but it helps you understand your options before applications open."
        ),
        "keywords": "kuccpss,what is,platform,help,student,cluster points,career guidance",
        "order": 1,
    },
    {
        "category": "general",
        "question": "What is the KUCCPS cluster points formula?",
        "answer": (
            "The official KUCCPS cluster points formula is: "
            "Cluster Points = 48 × √((core midpoint marks ÷ 400) × (KCSE aggregate ÷ 84)). "
            "'Core midpoint marks' is the sum of the midpoint raw marks (out of 100) for your best 4 "
            "cluster subjects — e.g. A=90.2, A-=77.5, B+=71.0, B=66.0, B-=60.0, C+=56.0, C=50.0, "
            "C-=46.0, D+=40.0, D=36.0, D-=31.0, E=14.0. "
            "The KCSE aggregate (max 84) = Mathematics + best of (English or Kiswahili) + next 5 best subjects. "
            "Maximum cluster points = 48. Different courses use different cluster subject groups."
        ),
        "keywords": "cluster points,formula,calculate,kuccps,aggregate,how calculated,maximum,48",
        "order": 2,
    },
    {
        "category": "general",
        "question": "What grade points are used in Kenya (A=?, B+=?, etc.)?",
        "answer": (
            "Kenya KCSE grade to points conversion:\n"
            "A = 12, A- = 11, B+ = 10, B = 9, B- = 8, "
            "C+ = 7, C = 6, C- = 5, D+ = 4, D = 3, D- = 2, E = 1. "
            "These points are used in the cluster points formula and mean grade calculations."
        ),
        "keywords": "grade points,a,b+,c+,d+,conversion,kcse,points,grades",
        "order": 3,
    },
]


class Command(BaseCommand):
    help = "Seed AIKnowledgeEntry with verified Kenyan career guidance Q&A"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing entries before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = AIKnowledgeEntry.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing entries."))

        created = updated = skipped = 0
        for entry in ENTRIES:
            obj, was_created = AIKnowledgeEntry.objects.update_or_create(
                question=entry["question"],
                defaults={
                    "answer":    entry["answer"],
                    "keywords":  entry.get("keywords", ""),
                    "category":  entry["category"],
                    "order":     entry.get("order", 0),
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created}  Updated: {updated}  Total: {created + updated}"
            )
        )
