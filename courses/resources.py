from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Course, CourseType, CourseCategory, CourseOffering
from clusters.models import Cluster
from institutions.models import Institution


class CourseResource(resources.ModelResource):
    """
    Import/export basic course metadata (name, type, category, cluster, description).
    Use CourseOfferingResource to import cutoff points per institution.

    CSV columns: name, course_type, category, cluster, description
    """
    course_type = fields.Field(
        column_name='course_type',
        attribute='course_type',
        widget=ForeignKeyWidget(CourseType, field='name'),
    )
    category = fields.Field(
        column_name='category',
        attribute='category',
        widget=ForeignKeyWidget(CourseCategory, field='name'),
    )
    cluster = fields.Field(
        column_name='cluster',
        attribute='cluster',
        widget=ForeignKeyWidget(Cluster, field='name'),
    )

    class Meta:
        model = Course
        fields = ('id', 'name', 'course_type', 'category', 'cluster', 'description')
        import_id_fields = ['name', 'course_type']
        skip_unchanged = True
        report_skipped = True
        exclude = ('slug', 'pdf_file', 'created_at', 'updated_at', 'cutoff_points', 'core_subjects', 'institutions')
        encoding = 'utf-8-sig'


class CourseOfferingResource(resources.ModelResource):
    """
    Import cutoff points per institution from a CSV that mirrors the KUCCPS PDF format.

    CSV columns:
        course_name, course_type, institution, cutoff_2024, cutoff_2023, cutoff_2022, cutoff_2021

    - course_name  : programme name (created automatically if missing)
    - course_type  : e.g. "Degree", "Diploma", "KMTC"  (created automatically if missing)
    - institution  : exact institution name as stored in the database
    - cutoff_YEAR  : numeric cutoff; leave blank if unknown
    """

    # All columns read directly from CSV — no FK widget magic
    course_name     = fields.Field(column_name='course_name', attribute=None)
    course_type_col = fields.Field(column_name='course_type', attribute=None)
    institution_col = fields.Field(column_name='institution', attribute=None)
    cutoff_2024     = fields.Field(column_name='cutoff_2024', attribute=None)
    cutoff_2023     = fields.Field(column_name='cutoff_2023', attribute=None)
    cutoff_2022     = fields.Field(column_name='cutoff_2022', attribute=None)
    cutoff_2021     = fields.Field(column_name='cutoff_2021', attribute=None)

    class Meta:
        model = CourseOffering
        fields = ('course_name', 'course_type_col', 'institution_col',
                  'cutoff_2024', 'cutoff_2023', 'cutoff_2022', 'cutoff_2021')
        import_id_fields = ['course_name']
        skip_unchanged = False
        report_skipped = False
        exclude = ('id', 'course', 'institution', 'cutoff_points')
        encoding = 'utf-8-sig'

    def get_or_init_instance(self, instance_loader, row):
        """Look up existing CourseOffering by (course, institution); create new if not found."""
        course_name      = ' '.join((row.get('course_name') or '').split())
        course_type_name = ' '.join((row.get('course_type') or '').split())
        institution_name = ' '.join((row.get('institution') or '').split())

        course = institution = None

        if course_name and course_type_name:
            ct, _ = CourseType.objects.get_or_create(name=course_type_name)
            course, _ = Course.objects.get_or_create(name=course_name, course_type=ct)

        if institution_name:
            institution = Institution.objects.filter(name=institution_name).first()

        if course and institution:
            existing = CourseOffering.objects.filter(course=course, institution=institution).first()
            if existing:
                return existing, False
            return CourseOffering(course=course, institution=institution), True

        # Row missing required data — return unsaveable blank instance
        return CourseOffering(), True

    def before_save_instance(self, instance, row, **kwargs):
        """Build cutoff_points JSONField from individual year columns."""
        if not instance.course_id or not instance.institution_id:
            raise Exception(
                f"Skipping row — institution not found: {row.get('institution', '')!r}"
            )
        cutoffs = {}
        for year in ('2024', '2023', '2022', '2021'):
            val = str(row.get(f'cutoff_{year}') or '').strip()
            if val:
                try:
                    cutoffs[year] = float(val)
                except ValueError:
                    pass
        instance.cutoff_points = cutoffs if cutoffs else None

    def skip_row(self, instance, original, row, import_validation_errors=None):
        return False

    # Export: reconstruct CSV columns from model instance
    def dehydrate_course_name(self, obj):
        return obj.course.name if obj.course else ''

    def dehydrate_course_type_col(self, obj):
        return obj.course.course_type.name if obj.course and obj.course.course_type else ''

    def dehydrate_institution_col(self, obj):
        return obj.institution.name if obj.institution else ''

    def dehydrate_cutoff_2024(self, obj):
        return (obj.cutoff_points or {}).get('2024', '')

    def dehydrate_cutoff_2023(self, obj):
        return (obj.cutoff_points or {}).get('2023', '')

    def dehydrate_cutoff_2022(self, obj):
        return (obj.cutoff_points or {}).get('2022', '')

    def dehydrate_cutoff_2021(self, obj):
        return (obj.cutoff_points or {}).get('2021', '')
