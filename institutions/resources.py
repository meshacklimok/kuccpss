from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Institution, InstitutionType


class InstitutionResource(resources.ModelResource):
    """
    Import/export resource for Institution model.

    CSV column format:
        name, institution_type, location, website, email, phone, description

    - institution_type : exact name of an existing InstitutionType (e.g. "Public University")
    """

    institution_type = fields.Field(
        column_name='institution_type',
        attribute='institution_type',
        widget=ForeignKeyWidget(InstitutionType, field='name'),
    )

    class Meta:
        model = Institution
        fields = ('id', 'name', 'institution_type', 'location', 'website', 'email', 'phone', 'description')
        import_id_fields = ['name']
        skip_unchanged = True
        report_skipped = True
        exclude = ('slug', 'logo', 'pdf_file', 'created_at', 'updated_at')


class InstitutionTypeResource(resources.ModelResource):
    """
    Import/export resource for InstitutionType.

    CSV column format:
        name, description, icon, color_code
    """

    class Meta:
        model = InstitutionType
        fields = ('id', 'name', 'description', 'icon', 'color_code')
        import_id_fields = ['name']
        skip_unchanged = True
        report_skipped = True
        exclude = ('slug',)
