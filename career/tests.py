"""
End-to-end tests for the Career Engine: every pathway's input → loading →
results → PDF flow, plus quiz, AI chat (OpenAI mocked) and result sharing.
"""
import json
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings

from clusters.models import Cluster, Subject
from courses.models import Course, CourseOffering, CourseType
from institutions.models import Institution, InstitutionType
from payments.models import PaymentExemption
from career.models import CareerProfile, QuizOption, QuizQuestion

User = get_user_model()

# Grade points (A=12 … E=1) for a solid B+ student
GRADES = {
    'English': 10, 'Kiswahili': 9, 'Mathematics': 11, 'Biology': 10,
    'Chemistry': 9, 'Physics': 8, 'Geography': 9, 'Christian Religious Education': 10,
}


def _fake_openai_client():
    message = mock.Mock(content='Mocked AI answer about courses.', tool_calls=None, role='assistant')
    response = mock.Mock(
        choices=[mock.Mock(message=message, finish_reason='stop')],
        usage=mock.Mock(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        model='mock',
    )
    client = mock.MagicMock()
    client.chat.completions.create.return_value = response
    return client


class CareerTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_clusters', stdout=StringIO())

        uni = InstitutionType.objects.create(name='University')
        tvet = InstitutionType.objects.create(name='TVET')
        kmtc = InstitutionType.objects.create(name='KMTC Campus')
        ttc = InstitutionType.objects.create(name='Teacher Training College')
        cls.university = Institution.objects.create(name='Test University', institution_type=uni)
        tvet_inst = Institution.objects.create(name='Test Technical Institute', institution_type=tvet)
        kmtc_inst = Institution.objects.create(name='Test KMTC Campus', institution_type=kmtc)
        ttc_inst = Institution.objects.create(name='Test Teachers College', institution_type=ttc)

        cluster = Cluster.objects.get(number=101)
        cls.degree_course = Course.objects.create(
            name='Bachelor of Laws Test', course_type=CourseType.objects.create(name='Degree'),
            cluster=cluster, minimum_mean_grade='C+',
        )
        CourseOffering.objects.create(
            course=cls.degree_course, institution=cls.university, cutoff_points={'2025': 30.0},
        )

        non_degree = [
            ('Diploma in Testing', 'TVET Diploma (Level 6)', 'C-', tvet_inst),
            ('Certificate in Testing', 'TVET Certificate (Level 5)', 'D', tvet_inst),
            ('Artisan in Testing', 'TVET Artisan Certificate (Level 4)', 'E', tvet_inst),
            ('Diploma in Clinical Testing', 'KMTC', 'C', kmtc_inst),
            ('Diploma in Teacher Testing', 'TTC', 'C', ttc_inst),
        ]
        for name, type_name, grade, inst in non_degree:
            course = Course.objects.create(
                name=name, course_type=CourseType.objects.create(name=type_name),
                minimum_mean_grade=grade,
            )
            CourseOffering.objects.create(course=course, institution=inst)

        cls.profile = CareerProfile.objects.create(title='Lawyer', description='Practises law.')
        for i in range(3):
            q = QuizQuestion.objects.create(text=f'Question {i}?', order=i)
            QuizOption.objects.create(question=q, text='Yes', career_tags='law', order=1)
            QuizOption.objects.create(question=q, text='No', career_tags='science', order=2)

        cls.user = User.objects.create_user(email='student@example.com', password='Pass12345!x')
        PaymentExemption.objects.create(user=cls.user, feature='')

    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        self.client.force_login(self.user)

    def grades_post(self, grades=GRADES):
        return {
            f'subject_{s.pk}': grades[s.name]
            for s in Subject.objects.filter(name__in=grades)
        }

    def assert_pdf(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, url)
        self.assertEqual(r['Content-Type'], 'application/pdf', url)


class DegreePathwayTests(CareerTestBase):

    def test_calculate_flow_reaches_results_with_matching_course(self):
        r = self.client.post('/career/degree/calculate/', self.grades_post())
        self.assertRedirects(r, '/career/degree/options/', fetch_redirect_response=False)
        r = self.client.post('/career/degree/options/', {'action': 'calculate'})
        self.assertRedirects(r, '/career/loading/degree/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/career/loading/degree/').status_code, 200)

        r = self.client.get('/career/results/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.degree_course.name)

    def test_results_pdfs(self):
        self.client.post('/career/degree/calculate/', self.grades_post())
        self.client.post('/career/degree/options/', {'action': 'calculate'})
        self.assert_pdf('/career/results/pdf/quick/')
        self.assert_pdf('/career/results/pdf/report/')

    def test_results_with_filters(self):
        self.client.post('/career/degree/calculate/', self.grades_post())
        self.client.post('/career/degree/options/', {'action': 'calculate'})
        r = self.client.get('/career/results/?q=laws&tier=safe&sort=points')
        self.assertEqual(r.status_code, 200)

    def test_paste_named_clusters(self):
        r = self.client.post('/career/degree/paste/', {'cluster_data': 'Cluster 1 40.5\nCluster 2 38.2'})
        self.assertRedirects(r, '/career/loading/degree/', fetch_redirect_response=False)
        r = self.client.get('/career/results/')
        self.assertContains(r, self.degree_course.name)

    def test_paste_plain_numbers(self):
        r = self.client.post('/career/degree/paste/', {'cluster_data': '40 31 32 33 34'})
        self.assertRedirects(r, '/career/loading/degree/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/career/results/').status_code, 200)

    def test_paste_garbage_does_not_error(self):
        r = self.client.post('/career/degree/paste/', {'cluster_data': 'hello'}, follow=True)
        self.assertEqual(r.status_code, 200)

    def test_manual_entry(self):
        r = self.client.post('/career/degree/manual/', {f'group_{i}': 40 for i in range(1, 19)})
        self.assertRedirects(r, '/career/loading/degree/', fetch_redirect_response=False)
        r = self.client.get('/career/results/')
        self.assertContains(r, self.degree_course.name)

    def test_manual_entry_clamps_out_of_range_values(self):
        r = self.client.post('/career/degree/manual/', {'group_1': '999', 'group_2': '-5', 'group_3': 'abc'})
        self.assertRedirects(r, '/career/loading/degree/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/career/results/').status_code, 200)


class GradeLockTests(CareerTestBase):
    """Grace-period review: Edit keeps previous grades; Confirm & Lock locks them."""

    def setUp(self):
        super().setUp()
        from career.models import SubmissionLockConfig
        SubmissionLockConfig.objects.create(feature='degree_career', lock_minutes=5)

    def _submission(self):
        from career.models import CareerSubmission
        return CareerSubmission.objects.get(user=self.user, feature='degree_career')

    def test_edit_prefills_previous_grades(self):
        self.client.post('/career/degree/calculate/', self.grades_post())
        r = self.client.get('/career/degree/calculate/')
        math = Subject.objects.get(name='Mathematics')
        # Mathematics was 11 (A-) — its option must render selected, not an empty form
        self.assertRegex(r.content.decode(), rf'name="subject_{math.pk}"[\s\S]*?value="11"\s+selected')

    def test_results_banner_lists_submitted_grades(self):
        self.client.post('/career/degree/calculate/', self.grades_post())
        self.client.post('/career/degree/options/', {'action': 'calculate'})
        self.client.get('/career/loading/degree/')
        r = self.client.get('/career/results/')
        self.assertContains(r, 'sub-lock-banner')
        self.assertContains(r, 'Mathematics <b>A-</b>', html=False)

    def test_confirm_locks_and_is_idempotent(self):
        self.client.post('/career/degree/calculate/', self.grades_post())
        for _ in range(2):
            r = self.client.post('/career/submission/confirm/', json.dumps({'feature': 'degree_career'}),
                                 content_type='application/json')
            self.assertEqual(r.status_code, 200)
        self.assertEqual(self._submission().status, 'locked')

    def test_confirm_rejects_bad_json(self):
        r = self.client.post('/career/submission/confirm/', 'not json', content_type='application/json')
        self.assertEqual(r.status_code, 400)


class NonDegreeGradeLockTests(CareerTestBase):
    """Diploma / Certificate / KMTC / TTC / Artisan share one grade lock."""

    def setUp(self):
        super().setUp()
        from career.models import SubmissionLockConfig
        SubmissionLockConfig.objects.update_or_create(
            feature='non_degree_career', defaults={'lock_minutes': 5, 'is_enabled': True},
        )

    def _submission(self):
        from career.models import CareerSubmission
        return CareerSubmission.objects.get(user=self.user, feature='non_degree_career')

    def _lock(self):
        r = self.client.post('/career/submission/confirm/', json.dumps({'feature': 'non_degree_career'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)

    def test_submit_starts_review_window(self):
        self.client.post('/career/input/diploma/', self.grades_post())
        sub = self._submission()
        self.assertEqual((sub.status, sub.method), ('pending', 'calculate'))
        r = self.client.get('/career/results/')
        self.assertContains(r, 'sub-lock-banner')
        self.assertContains(r, 'Mathematics <b>A-</b>', html=False)

    def test_ttc_mean_grade_is_locked_too(self):
        self.client.post('/career/input/ttc/', {'mean_grade': 'C+'})
        sub = self._submission()
        self.assertEqual((sub.method, sub.grades_json), ('manual', {'mean_grade': 'C+'}))
        self.assertContains(self.client.get('/career/results/'), 'Mean grade <b>C+</b>', html=False)

    def test_locked_grades_ignore_new_submissions(self):
        self.client.post('/career/input/diploma/', self.grades_post())
        mean = self.client.session['career_mean_grade']
        self._lock()
        # Switch pathway and try all-E grades: the locked grades must win
        r = self.client.post('/career/input/kmtc/', self.grades_post({k: 1 for k in GRADES}))
        self.assertRedirects(r, '/career/loading/kmtc/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['career_mean_grade'], mean)
        self.assertEqual(self.client.session['career_pathway'], 'KMTC')
        self.assertEqual(self._submission().grades_json, GRADES)

    def test_locked_input_page_is_read_only(self):
        self.client.post('/career/input/diploma/', self.grades_post())
        self._lock()
        r = self.client.get('/career/input/certificate/')
        self.assertContains(r, 'Your grades are locked')
        math = Subject.objects.get(name='Mathematics')
        self.assertRegex(r.content.decode(), rf'name="subject_{math.pk}"[^>]*disabled')

    def test_locked_results_hide_edit_grades(self):
        self.client.post('/career/input/diploma/', self.grades_post())
        self._lock()
        r = self.client.get('/career/results/')
        self.assertNotContains(r, 'hero-edit-grades-btn')
        self.assertNotContains(r, 'sub-lock-banner')

    def test_expired_window_auto_locks(self):
        from django.utils import timezone
        from datetime import timedelta
        self.client.post('/career/input/diploma/', self.grades_post())
        sub = self._submission()
        sub.lock_at = timezone.now() - timedelta(seconds=1)
        sub.save(update_fields=['lock_at'])
        self.client.get('/career/input/diploma/')
        self.assertEqual(self._submission().status, 'locked')

    def test_recalculate_unlocks_only_non_degree(self):
        from career.models import CareerSubmission, SubmissionLockConfig
        SubmissionLockConfig.objects.update_or_create(feature='degree_career', defaults={'lock_minutes': 5})
        self.client.post('/career/degree/calculate/', self.grades_post())
        self.client.post('/career/input/diploma/', self.grades_post())
        self._lock()
        r = self.client.post('/career/submission/recalculate/', {'pathway': 'diploma'})
        self.assertRedirects(r, '/career/input/diploma/', fetch_redirect_response=False)
        self.assertFalse(CareerSubmission.objects.filter(user=self.user, feature='non_degree_career').exists())
        self.assertTrue(CareerSubmission.objects.filter(user=self.user, feature='degree_career').exists())


class NonDegreePathwayTests(CareerTestBase):

    def test_kcse_form_pathways_reach_results(self):
        expected = {
            'diploma': 'Diploma in Testing',
            'certificate': 'Certificate in Testing',
            'kmtc': 'Diploma in Clinical Testing',
            'artisan': 'Artisan in Testing',
        }
        for pathway, course_name in expected.items():
            with self.subTest(pathway=pathway):
                r = self.client.post(f'/career/input/{pathway}/', self.grades_post())
                self.assertRedirects(r, f'/career/loading/{pathway}/', fetch_redirect_response=False)
                r = self.client.get('/career/results/')
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, course_name)
                self.assert_pdf('/career/results/pdf/quick/')
                self.assert_pdf('/career/results/pdf/report/')
                self.assertEqual(self.client.get(f'/career/input/{pathway}/?edit=1').status_code, 200)

    def test_ttc_mean_grade_pathway(self):
        r = self.client.post('/career/input/ttc/', {'mean_grade': 'C+'})
        self.assertRedirects(r, '/career/loading/ttc/', fetch_redirect_response=False)
        r = self.client.get('/career/results/')
        self.assertContains(r, 'Diploma in Teacher Testing')

    def test_low_mean_grades_do_not_error(self):
        for grade in ('D', 'E'):
            with self.subTest(grade=grade):
                self.client.post('/career/input/ttc/', {'mean_grade': grade})
                self.assertEqual(self.client.get('/career/results/').status_code, 200)

    def test_empty_mean_grade_bounces_to_home(self):
        self.client.post('/career/input/ttc/', {'mean_grade': ''})
        r = self.client.get('/career/loading/ttc/')
        self.assertRedirects(r, '/career/', fetch_redirect_response=False)

    def test_too_few_subjects_rerenders_with_error(self):
        grades = {k: GRADES[k] for k in ('English', 'Kiswahili', 'Mathematics')}
        r = self.client.post('/career/input/diploma/', self.grades_post(grades))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'at least 7 subjects')

    def test_unknown_pathway_redirects_home(self):
        r = self.client.get('/career/input/nonsense/')
        self.assertRedirects(r, '/career/', fetch_redirect_response=False)

    def test_guest_is_sent_to_register(self):
        self.client.logout()
        r = self.client.post('/career/input/diploma/', self.grades_post())
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/register/', r['Location'])

    def test_results_without_session_redirect(self):
        self.client.post('/career/clear/')
        r = self.client.get('/career/results/')
        self.assertEqual(r.status_code, 302)


class QuizTests(CareerTestBase):

    def test_submit_quiz_and_view_results(self):
        answers = {f'q_{q.pk}': q.options.first().pk for q in QuizQuestion.objects.all()}
        r = self.client.post('/career/quiz/', answers)
        self.assertRedirects(r, '/career/quiz/results/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['quiz_tag_scores'], {'law': 3})
        self.assertEqual(self.client.get('/career/quiz/results/').status_code, 200)

    def test_anonymous_quiz_and_bogus_option_ids(self):
        self.client.logout()
        answers = {f'q_{q.pk}': 999999 for q in QuizQuestion.objects.all()}
        r = self.client.post('/career/quiz/', answers)
        self.assertRedirects(r, '/career/quiz/results/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['quiz_tag_scores'], {})


@override_settings(OPENAI_API_KEY='sk-test')
class AIChatTests(CareerTestBase):
    URL = '/career/ajax/ai-chat/'

    def chat(self, body):
        return self.client.post(self.URL, body, content_type='application/json')

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.chat(json.dumps({'message': 'hi'})).status_code, 401)

    @override_settings(OPENAI_API_KEY='')
    def test_not_configured(self):
        self.assertEqual(self.chat(json.dumps({'message': 'hi'})).status_code, 400)

    def test_rejects_bad_input(self):
        self.assertEqual(self.chat('not json').status_code, 400)
        self.assertEqual(self.chat(json.dumps({'message': '  '})).status_code, 400)

    def test_mocked_reply(self):
        with mock.patch('kuccpss.circuit_breaker.get_openai_client', return_value=_fake_openai_client()):
            r = self.chat(json.dumps({'message': 'Which law courses can I get?', 'history': []}))
        self.assertEqual(r.status_code, 200)
        self.assertIn('Mocked AI answer', r.content.decode())

    def test_chat_page_renders(self):
        self.assertEqual(self.client.get('/career/chat/').status_code, 200)

    def test_json_reply_splits_followups(self):
        msg = SimpleNamespace(content='**Hi!**\n<<FOLLOWUPS: What can I study? | Explain cluster points>>',
                              tool_calls=None)
        client = mock.MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        with mock.patch('kuccpss.circuit_breaker.get_openai_client', return_value=client):
            data = self.chat(json.dumps({'message': 'hi'})).json()
        self.assertEqual(data['reply'], '**Hi!**')
        self.assertEqual(data['followups'], ['What can I study?', 'Explain cluster points'])

    def test_tool_call_reads_database_before_answering(self):
        """The model asks for course details; the DB result is fed back before the final answer."""
        call = SimpleNamespace(id='call_1', function=SimpleNamespace(
            name='get_course_details', arguments=json.dumps({'course_name': 'law'})))
        first = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))])
        second = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='You can study law at Test University.', tool_calls=None))])
        client = mock.MagicMock()
        client.chat.completions.create.side_effect = [first, second]
        with mock.patch('kuccpss.circuit_breaker.get_openai_client', return_value=client):
            r = self.chat(json.dumps({'message': 'Can I do law?', 'history': []}))
        self.assertEqual(r.json()['reply'], 'You can study law at Test University.')
        final_messages = client.chat.completions.create.call_args_list[1].kwargs['messages']
        tool_msg = next(m for m in final_messages if m['role'] == 'tool')
        self.assertIn('Test University', tool_msg['content'])
        self.assertIn('Bachelor of Laws Test', tool_msg['content'])

    def test_streaming_tool_call_then_answer(self):
        def chunk(content=None, tool_calls=None):
            return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
                content=content, tool_calls=tool_calls))])
        tc = SimpleNamespace(index=0, id='call_9', function=SimpleNamespace(
            name='search_institutions', arguments='{"query": "Test University"}'))
        client = mock.MagicMock()
        client.chat.completions.create.side_effect = [
            iter([chunk(tool_calls=[tc])]),
            iter([chunk('Found '), chunk('it!')]),
        ]
        with mock.patch('kuccpss.circuit_breaker.get_openai_client', return_value=client):
            r = self.chat(json.dumps({'message': 'Where is Test University?', 'stream': True}))
        self.assertEqual(b''.join(r.streaming_content).decode(), 'Found it!')
        tool_msg = client.chat.completions.create.call_args_list[1].kwargs['messages'][-1]
        self.assertEqual(tool_msg['role'], 'tool')
        self.assertIn('Test University', tool_msg['content'])


class AIAssistantTests(CareerTestBase):
    """career/ai_assistant.py — prompt content, site map and database tools."""

    def setUp(self):
        super().setUp()
        from career import ai_assistant
        self.ai = ai_assistant
        self.student = {
            'pathway': 'Degree', 'mean_grade': 'B+',
            'subject_grades': {'english': 10, 'mathematics': 11},
            'cluster_points': {'1': 32.5}, 'snapshot': None,
        }

    def test_site_guide_paths_resolve(self):
        from django.urls import resolve
        for title, path, _ in self.ai.SITE_PAGES:
            with self.subTest(page=title):
                resolve(path.split('?')[0])

    def test_prompt_knows_identity_and_navigation(self):
        prompt = self.ai.SYSTEM_PROMPT_STATIC
        self.assertIn('Meshack Limo', prompt)
        self.assertIn('/clusterpoints/calculator/', prompt)
        self.assertIn('Cluster 13: Medicine', prompt)
        self.assertIn('POINT FORM, SUMMARY FIRST', prompt)
        self.assertIn('NEVER answer with a block paragraph', prompt)

    def test_course_details_include_eligibility(self):
        out = self.ai.tool_get_course_details(self.student, 'Bachelor of Laws')
        row = out['offered_at'][0]
        self.assertEqual(row['institution'], 'Test University')
        self.assertEqual(row['for_this_student']['margin'], 2.5)
        self.assertEqual(row['for_this_student']['status'], '🟢 Strong Match')

    def test_zero_cluster_points_is_not_eligible(self):
        self.student['cluster_points'] = {'1': 0.0}
        out = self.ai.tool_get_course_details(self.student, 'law')
        self.assertEqual(out['offered_at'][0]['for_this_student']['status'], '🔴 Not Eligible')

    def test_find_courses_i_qualify_for(self):
        degree = self.ai.tool_find_courses_i_qualify_for(self.student, 'degree')
        self.assertEqual(degree['results'][0]['course'], 'Bachelor of Laws Test')
        kmtc = self.ai.tool_find_courses_i_qualify_for({**self.student, 'mean_grade': 'C-'}, 'kmtc')
        self.assertEqual(kmtc['results'], [])   # KMTC course needs C
        self.assertIn('error', self.ai.tool_find_courses_i_qualify_for(
            {'cluster_points': {}, 'mean_grade': '', 'subject_grades': {}}, 'degree'))

    def test_institution_and_career_lookups(self):
        inst = self.ai.tool_get_institution_courses(self.student, 'Test KMTC Campus')
        self.assertEqual(inst['courses'][0]['course'], 'Diploma in Clinical Testing')
        careers = self.ai.tool_search_careers(self.student, 'lawyer')
        self.assertEqual(careers['results'][0]['career'], 'Lawyer')

    def test_run_tool_handles_bad_input(self):
        self.assertIn('Unknown tool', self.ai.run_tool('drop_tables', '{}', self.student))
        self.assertIn('Bad arguments', self.ai.run_tool('search_courses', '{"nope": 1}', self.student))

    def test_split_followups(self):
        reply, followups = self.ai.split_followups(
            '**Yes.**\n- point\n<<FOLLOWUPS: Compare law vs medicine | Where is it offered? >>')
        self.assertEqual(reply, '**Yes.**\n- point')
        self.assertEqual(followups, ['Compare law vs medicine', 'Where is it offered?'])
        self.assertEqual(self.ai.split_followups('plain'), ('plain', []))

    def test_course_details_include_cutoff_prediction(self):
        row = self.ai.tool_get_course_details(self.student, 'law')['offered_at'][0]
        pred = row['predicted_next_cutoff']
        self.assertEqual(pred['years_of_data'], 1)
        self.assertIn('your_chance', pred)

    def test_compare_courses(self):
        out = self.ai.tool_compare_courses(self.student, ['law', 'Diploma in Testing'])
        law, dip = out['comparison']
        self.assertEqual(law['name'], 'Bachelor of Laws Test')
        self.assertEqual(law['you_qualify_at'], 1)
        self.assertEqual(law['best_option']['institution'], 'Test University')
        self.assertEqual(law['your_cluster_points'], 32.5)
        self.assertEqual(dip['name'], 'Diploma in Testing')
        self.assertIn('error', self.ai.tool_compare_courses(self.student, ['law']))

    def test_salary_outlook(self):
        from career.models import JobMarketData
        JobMarketData.objects.create(career_name='Advocate', keywords='advocate,lawyer',
                                     salary_min=80000, salary_max=250000, demand='High',
                                     top_sectors='Law firms, Judiciary')
        out = self.ai.tool_get_salary_outlook(self.student, 'advocate')
        self.assertEqual(out['monthly_salary_kes'], '80,000–250,000')
        self.assertIn('error', self.ai.tool_get_salary_outlook(self.student, 'astronaut'))

    def test_my_shortlist(self):
        from accounts.models import CourseShortlist
        self.assertIn('error', self.ai.tool_get_my_shortlist(self.student))   # anonymous
        CourseShortlist.objects.create(user=self.user, course=self.degree_course, rank=1, notes='Dream course')
        out = self.ai.tool_get_my_shortlist({**self.student, 'user_id': self.user.pk})
        item = out['shortlist'][0]
        self.assertEqual((item['rank'], item['name'], item['notes']), (1, 'Bachelor of Laws Test', 'Dream course'))
        self.assertEqual(item['you_qualify_at'], 1)

    def test_every_tool_has_a_spec(self):
        specs = {t['function']['name'] for t in self.ai.TOOL_SPECS}
        self.assertEqual(specs, set(self.ai._TOOL_FUNCS))


class ShareResultTests(CareerTestBase):

    def test_share_without_results_is_rejected(self):
        self.client.post('/career/clear/')
        r = self.client.post('/career/share/create/')
        self.assertEqual(r.status_code, 400)

    def test_share_after_results(self):
        self.client.post('/career/degree/manual/', {f'group_{i}': 40 for i in range(1, 19)})
        self.client.get('/career/results/')
        r = self.client.post('/career/share/create/')
        self.assertEqual(r.status_code, 200)
        url = r.json()['url'].replace('http://testserver', '')
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 200)


class CareerPagesSmokeTests(CareerTestBase):
    PAGES = [
        '/career/', '/career/kcse-input/', '/career/profiles/', '/career/quiz/',
        '/career/degree/', '/career/degree/calculate/', '/career/degree/options/',
        '/career/degree/upload/', '/career/degree/paste/', '/career/degree/manual/',
        '/career/input/degree/', '/career/input/diploma/', '/career/input/ttc/',
        '/career/search-courses/?q=law', '/career/search-courses/?q=%3Cscript%3E',
        '/career/ai-recommendations/', '/career/export-matches/',
    ]

    def test_pages_render_for_anonymous_and_logged_in(self):
        for logged_in in (False, True):
            if not logged_in:
                self.client.logout()
            else:
                self.client.force_login(self.user)
            for url in self.PAGES + [f'/career/profiles/{self.profile.slug}/']:
                with self.subTest(url=url, logged_in=logged_in):
                    self.assertLess(self.client.get(url).status_code, 500)


class RetiredCareerPagesTests(CareerTestBase):
    """The old KCSE-input flow (legacy career.Course tables) now 301s to the engine."""

    def test_legacy_pages_redirect_to_engine(self):
        for url in ('/career/kcse-input/', '/career/course/5/', '/career/filter-matches/',
                    '/career/ai-recommendations/', '/career/search-courses/?q=law',
                    '/career/export-matches/'):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), '/career/',
                                     status_code=301, fetch_redirect_response=False)

    def test_kcse_input_keeps_pathway(self):
        self.assertRedirects(self.client.get('/career/kcse-input/?pathway=KMTC'),
                             '/career/input/kmtc/', status_code=301, fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/career/kcse-input/?pathway=nonsense'),
                             '/career/', status_code=301, fetch_redirect_response=False)


class AIAssistantActionToolTests(CareerTestBase):
    """Newer CareerNext AI tools: cluster working, what-if, choice planner, careers, actions."""

    def setUp(self):
        super().setUp()
        from career import ai_assistant
        self.ai = ai_assistant
        grades = {k.lower(): v for k, v in GRADES.items()}
        pts = {str(r.cluster.kuccps_number): r.cluster_points
               for r in self._clusters(GRADES) if r.cluster.kuccps_number}
        self.student = {
            'pathway': 'Degree', 'mean_grade': 'B+', 'subject_grades': grades,
            'cluster_points': pts, 'snapshot': None, 'user_id': self.user.pk, 'quiz_tags': {},
        }

    @staticmethod
    def _clusters(grades):
        from clusterpoints.services import calculate_clusters_anonymous
        return calculate_clusters_anonymous(grades)

    def test_every_tool_spec_has_an_implementation(self):
        for spec in self.ai.TOOL_SPECS:
            self.assertIn(spec['function']['name'], self.ai._TOOL_FUNCS)

    def test_aggregate_subjects_matches_aggregate_total(self):
        from clusterpoints.services import aggregate_subjects, compute_aggregate_total
        picked = aggregate_subjects(GRADES)
        self.assertEqual(len(picked), 7)
        self.assertEqual(picked[0][0], 'Mathematics')
        self.assertEqual(picked[1][0], 'English')
        self.assertEqual(sum(p for _, p in picked), compute_aggregate_total(GRADES))

    def test_explain_cluster_points_shows_formula_and_matches_calculator(self):
        out = self.ai.tool_explain_my_cluster_points(self.student, 1)
        self.assertEqual(len(out['cluster_subjects']), 4)
        self.assertIn('48 × √', out['formula'])
        self.assertAlmostEqual(out['cluster_points'], float(self.student['cluster_points']['1']), places=3)
        self.assertNotIn('note', out)

    def test_simulate_grade_change_raises_points_and_rechecks_course(self):
        out = self.ai.tool_simulate_grade_change(
            self.student, [{'subject': 'english', 'grade': 'A'}], course_name='law')
        self.assertIn('English: B+ → A', out['changes_applied'])
        law = next(d for d in out['cluster_changes'] if d['cluster'] == 1)
        self.assertGreater(law['change'], 0)
        self.assertIn('with_changes', out['course_check'])

    def test_simulate_rejects_invalid_grade(self):
        out = self.ai.tool_simulate_grade_change(self.student, [{'subject': 'english', 'grade': 'Z'}])
        self.assertIn('error', out)

    def test_plan_kuccps_choices_buckets_eligible_course(self):
        self.student['cluster_points']['1'] = 32.5   # cutoff 30.0 → +2.5 → Safe
        out = self.ai.tool_plan_kuccps_choices(self.student, level='degree')
        self.assertEqual(out['plan'][0]['course'], 'Bachelor of Laws Test')
        self.assertEqual(out['plan'][0]['tier'], 'Safe')

    def test_recommend_careers_uses_quiz_and_eligibility(self):
        self.profile.career_tags = 'law'
        self.profile.save()
        self.profile.related_courses.add(self.degree_course)
        self.student['cluster_points']['1'] = 32.5
        self.student['quiz_tags'] = {'law': 3}
        out = self.ai.tool_recommend_careers_for_me(self.student)
        self.assertEqual(out['results'][0]['career'], 'Lawyer')
        self.assertEqual(out['results'][0]['fit'], 'Excellent fit')

    def test_recommend_careers_without_interests_asks(self):
        self.assertIn('error', self.ai.tool_recommend_careers_for_me(self.student))

    def test_add_to_shortlist_with_rank_and_limit(self):
        from accounts.models import CourseShortlist
        out = self.ai.tool_add_to_shortlist(self.student, 'Bachelor of Laws', rank=1, note='Top pick')
        self.assertEqual(out['result'], 'added')
        item = CourseShortlist.objects.get(user=self.user, course=self.degree_course)
        self.assertEqual((item.rank, item.notes), (1, 'Top pick'))
        for c in Course.objects.exclude(pk=self.degree_course.pk)[:4]:
            CourseShortlist.objects.create(user=self.user, course=c)
        extra = Course.objects.create(name='Extra Testing Course', course_type=self.degree_course.course_type)
        out = self.ai.tool_add_to_shortlist(self.student, extra.name)
        self.assertIn('full', out['error'])

    def test_add_to_shortlist_requires_login(self):
        self.student['user_id'] = None
        self.assertIn('error', self.ai.tool_add_to_shortlist(self.student, 'law'))

    def test_kuccps_calendar_lists_current_cycle(self):
        from resources.models import CalendarCycle, CalendarEvent
        cycle = CalendarCycle.objects.create(title='KCSE 2025 Cycle', tab_label='2025', is_current=True)
        CalendarEvent.objects.create(cycle=cycle, title='First application window', date_label='May 2026',
                                     status='active')
        out = self.ai.tool_get_kuccps_calendar(self.student)
        self.assertEqual(out['events'][0]['event'], 'First application window')
        self.assertEqual(out['events'][0]['status'], 'Open now')

    def test_location_filter(self):
        self.student['cluster_points']['1'] = 32.5
        self.assertEqual(self.ai.tool_find_courses_i_qualify_for(self.student, 'degree', location='Mombasa')['results'], [])
        self.assertTrue(self.ai.tool_find_courses_i_qualify_for(self.student, 'degree', location='Test')['results'])
