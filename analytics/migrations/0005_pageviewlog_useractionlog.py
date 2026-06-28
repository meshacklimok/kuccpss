from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0004_pwa_install_log'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PageViewLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(db_index=True, max_length=500)),
                ('method', models.CharField(default='GET', max_length=10)),
                ('status_code', models.PositiveSmallIntegerField(db_index=True, default=200)),
                ('response_time_ms', models.PositiveIntegerField(default=0)),
                ('referrer', models.CharField(blank=True, max_length=500)),
                ('device', models.CharField(
                    choices=[
                        ('mobile', 'Mobile'), ('tablet', 'Tablet'),
                        ('desktop', 'Desktop'), ('bot', 'Bot / Crawler'),
                        ('unknown', 'Unknown'),
                    ],
                    db_index=True, default='unknown', max_length=10,
                )),
                ('session_key', models.CharField(blank=True, max_length=40)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='pageviewlog',
            index=models.Index(fields=['path', 'created_at'], name='analytics_p_path_ca_idx'),
        ),
        migrations.AddIndex(
            model_name='pageviewlog',
            index=models.Index(fields=['status_code', 'created_at'], name='analytics_p_status_ca_idx'),
        ),
        migrations.AddIndex(
            model_name='pageviewlog',
            index=models.Index(fields=['device', 'created_at'], name='analytics_p_device_ca_idx'),
        ),
        migrations.CreateModel(
            name='UserActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(
                    choices=[
                        ('login', 'Login'), ('login_failed', 'Login Failed'),
                        ('logout', 'Logout'), ('shortlist_add', 'Shortlist Add'),
                        ('shortlist_remove', 'Shortlist Remove'), ('compare_add', 'Compare Add'),
                        ('compare_remove', 'Compare Remove'), ('profile_update', 'Profile Update'),
                        ('share', 'Share'), ('ai_chat', 'AI Chat Message'),
                        ('quiz_start', 'Quiz Start'), ('quiz_complete', 'Quiz Complete'),
                        ('calculator_run', 'Calculator Run'), ('referral_click', 'Referral Click'),
                        ('email_verified', 'Email Verified'), ('password_reset', 'Password Reset'),
                    ],
                    db_index=True, max_length=30,
                )),
                ('properties', models.JSONField(blank=True, default=dict)),
                ('session_key', models.CharField(blank=True, max_length=40)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='useractionlog',
            index=models.Index(fields=['action', 'created_at'], name='analytics_u_action_ca_idx'),
        ),
        migrations.AddIndex(
            model_name='useractionlog',
            index=models.Index(fields=['created_at'], name='analytics_u_created_idx'),
        ),
    ]
