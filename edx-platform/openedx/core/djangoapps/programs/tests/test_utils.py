"""Tests covering Programs utilities."""
# pylint: disable=no-member
import datetime
import uuid

import ddt
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.utils import override_settings
import mock
from nose.plugins.attrib import attr
from pytz import utc

from lms.djangoapps.certificates.api import MODES
from lms.djangoapps.commerce.tests.test_utils import update_commerce_config
from openedx.core.djangoapps.catalog.tests.factories import (
    generate_course_run_key,
    ProgramFactory,
    CourseFactory,
    CourseRunFactory,
)
from openedx.core.djangoapps.programs.tests.factories import ProgressFactory
from openedx.core.djangoapps.programs.utils import (
    DEFAULT_ENROLLMENT_START_DATE, ProgramProgressMeter, ProgramDataExtender
)
from openedx.core.djangolib.testing.utils import skip_unless_lms
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from util.date_utils import strftime_localized
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory as ModuleStoreCourseFactory


UTILS_MODULE = 'openedx.core.djangoapps.programs.utils'
CERTIFICATES_API_MODULE = 'lms.djangoapps.certificates.api'
ECOMMERCE_URL_ROOT = 'https://example-ecommerce.com'


@attr(shard=2)
@skip_unless_lms
@mock.patch(UTILS_MODULE + '.get_programs')
class TestProgramProgressMeter(TestCase):
    """Tests of the program progress utility class."""
    def setUp(self):
        super(TestProgramProgressMeter, self).setUp()

        self.user = UserFactory()

    def _create_enrollments(self, *course_run_ids):
        """Variadic helper used to create course run enrollments."""
        for course_run_id in course_run_ids:
            CourseEnrollmentFactory(user=self.user, course_id=course_run_id)

    def _assert_progress(self, meter, *progresses):
        """Variadic helper used to verify progress calculations."""
        self.assertEqual(meter.progress, list(progresses))

    def _attach_detail_url(self, programs):
        """Add expected detail URLs to a list of program dicts."""
        for program in programs:
            program['detail_url'] = reverse('program_details_view', kwargs={'program_uuid': program['uuid']})

    def test_no_enrollments(self, mock_get_programs):
        """Verify behavior when programs exist, but no relevant enrollments do."""
        data = [ProgramFactory()]
        mock_get_programs.return_value = data

        meter = ProgramProgressMeter(self.user)

        self.assertEqual(meter.engaged_programs, [])
        self._assert_progress(meter)
        self.assertEqual(meter.completed_programs, [])

    def test_no_programs(self, mock_get_programs):
        """Verify behavior when enrollments exist, but no matching programs do."""
        mock_get_programs.return_value = []

        course_run_id = generate_course_run_key()
        self._create_enrollments(course_run_id)
        meter = ProgramProgressMeter(self.user)

        self.assertEqual(meter.engaged_programs, [])
        self._assert_progress(meter)
        self.assertEqual(meter.completed_programs, [])

    def test_single_program_engagement(self, mock_get_programs):
        """
        Verify that correct program is returned when the user is enrolled in a
        course run appearing in one program.
        """
        course_run_key = generate_course_run_key()
        data = [
            ProgramFactory(
                courses=[
                    CourseFactory(course_runs=[
                        CourseRunFactory(key=course_run_key),
                    ]),
                ]
            ),
            ProgramFactory(),
        ]
        mock_get_programs.return_value = data

        self._create_enrollments(course_run_key)
        meter = ProgramProgressMeter(self.user)

        self._attach_detail_url(data)
        program = data[0]
        self.assertEqual(meter.engaged_programs, [program])
        self._assert_progress(
            meter,
            ProgressFactory(uuid=program['uuid'], in_progress=1)
        )
        self.assertEqual(meter.completed_programs, [])

    def test_mutiple_program_engagement(self, mock_get_programs):
        """
        Verify that correct programs are returned in the correct order when the
        user is enrolled in course runs appearing in programs.
        """
        newer_course_run_key, older_course_run_key = (generate_course_run_key() for __ in range(2))
        data = [
            ProgramFactory(
                courses=[
                    CourseFactory(course_runs=[
                        CourseRunFactory(key=newer_course_run_key),
                    ]),
                ]
            ),
            ProgramFactory(
                courses=[
                    CourseFactory(course_runs=[
                        CourseRunFactory(key=older_course_run_key),
                    ]),
                ]
            ),
            ProgramFactory(),
        ]
        mock_get_programs.return_value = data

        # The creation time of the enrollments matters to the test. We want
        # the first_course_run_key to represent the newest enrollment.
        self._create_enrollments(older_course_run_key, newer_course_run_key)
        meter = ProgramProgressMeter(self.user)

        self._attach_detail_url(data)
        programs = data[:2]
        self.assertEqual(meter.engaged_programs, programs)
        self._assert_progress(
            meter,
            *(ProgressFactory(uuid=program['uuid'], in_progress=1) for program in programs)
        )
        self.assertEqual(meter.completed_programs, [])

    def test_shared_enrollment_engagement(self, mock_get_programs):
        """
        Verify that correct programs are returned when the user is enrolled in a
        single course run appearing in multiple programs.
        """
        shared_course_run_key, solo_course_run_key = (generate_course_run_key() for __ in range(2))

        batch = [
            ProgramFactory(
                courses=[
                    CourseFactory(course_runs=[
                        CourseRunFactory(key=shared_course_run_key),
                    ]),
                ]
            )
            for __ in range(2)
        ]

        joint_programs = sorted(batch, key=lambda program: program['title'])
        data = joint_programs + [
            ProgramFactory(
                courses=[
                    CourseFactory(course_runs=[
                        CourseRunFactory(key=solo_course_run_key),
                    ]),
                ]
            ),
            ProgramFactory(),
        ]

        mock_get_programs.return_value = data

        # Enrollment for the shared course run created last (most recently).
        self._create_enrollments(solo_course_run_key, shared_course_run_key)
        meter = ProgramProgressMeter(self.user)

        self._attach_detail_url(data)
        programs = data[:3]
        self.assertEqual(meter.engaged_programs, programs)
        self._assert_progress(
            meter,
            *(ProgressFactory(uuid=program['uuid'], in_progress=1) for program in programs)
        )
        self.assertEqual(meter.completed_programs, [])

    @mock.patch(UTILS_MODULE + '.ProgramProgressMeter.completed_course_runs', new_callable=mock.PropertyMock)
    def test_simulate_progress(self, mock_completed_course_runs, mock_get_programs):
        """Simulate the entirety of a user's progress through a program."""
        first_course_run_key, second_course_run_key = (generate_course_run_key() for __ in range(2))
        data = [
            ProgramFactory(
                courses=[
                    CourseFactory(course_runs=[
                        CourseRunFactory(key=first_course_run_key),
                    ]),
                    CourseFactory(course_runs=[
                        CourseRunFactory(key=second_course_run_key),
                    ]),
                ]
            ),
            ProgramFactory(),
        ]
        mock_get_programs.return_value = data

        # No enrollments, no programs in progress.
        meter = ProgramProgressMeter(self.user)
        self._assert_progress(meter)
        self.assertEqual(meter.completed_programs, [])

        # One enrollment, one program in progress.
        self._create_enrollments(first_course_run_key)
        meter = ProgramProgressMeter(self.user)
        program, program_uuid = data[0], data[0]['uuid']
        self._assert_progress(
            meter,
            ProgressFactory(uuid=program_uuid, in_progress=1, not_started=1)
        )
        self.assertEqual(meter.completed_programs, [])

        # Two enrollments, all courses in progress.
        self._create_enrollments(second_course_run_key)
        meter = ProgramProgressMeter(self.user)
        self._assert_progress(
            meter,
            ProgressFactory(uuid=program_uuid, in_progress=2)
        )
        self.assertEqual(meter.completed_programs, [])

        # One valid certificate earned, one course complete.
        mock_completed_course_runs.return_value = [
            {'course_run_id': first_course_run_key, 'type': MODES.verified},
        ]
        meter = ProgramProgressMeter(self.user)
        self._assert_progress(
            meter,
            ProgressFactory(uuid=program_uuid, completed=1, in_progress=1)
        )
        self.assertEqual(meter.completed_programs, [])

        # Invalid certificate earned, still one course to complete.
        mock_completed_course_runs.return_value = [
            {'course_run_id': first_course_run_key, 'type': MODES.verified},
            {'course_run_id': second_course_run_key, 'type': MODES.honor},
        ]
        meter = ProgramProgressMeter(self.user)
        self._assert_progress(
            meter,
            ProgressFactory(uuid=program_uuid, completed=1, in_progress=1)
        )
        self.assertEqual(meter.completed_programs, [])

        # Second valid certificate obtained, all courses complete.
        mock_completed_course_runs.return_value = [
            {'course_run_id': first_course_run_key, 'type': MODES.verified},
            {'course_run_id': second_course_run_key, 'type': MODES.verified},
        ]
        meter = ProgramProgressMeter(self.user)
        self._assert_progress(
            meter,
            ProgressFactory(uuid=program_uuid, completed=2)
        )
        self.assertEqual(meter.completed_programs, [program_uuid])

    @mock.patch(UTILS_MODULE + '.ProgramProgressMeter.completed_course_runs', new_callable=mock.PropertyMock)
    def test_nonverified_course_run_completion(self, mock_completed_course_runs, mock_get_programs):
        """
        Course runs aren't necessarily of type verified. Verify that a program can
        still be completed when this is the case.
        """
        course_run_key = generate_course_run_key()
        data = [
            ProgramFactory(
                courses=[
                    CourseFactory(course_runs=[
                        CourseRunFactory(key=course_run_key, type='honor'),
                        CourseRunFactory(),
                    ]),
                ]
            ),
            ProgramFactory(),
        ]
        mock_get_programs.return_value = data

        self._create_enrollments(course_run_key)
        mock_completed_course_runs.return_value = [
            {'course_run_id': course_run_key, 'type': MODES.honor},
        ]
        meter = ProgramProgressMeter(self.user)

        program, program_uuid = data[0], data[0]['uuid']
        self._assert_progress(
            meter,
            ProgressFactory(uuid=program_uuid, completed=1)
        )
        self.assertEqual(meter.completed_programs, [program_uuid])

    @mock.patch(UTILS_MODULE + '.ProgramProgressMeter.completed_course_runs', new_callable=mock.PropertyMock)
    def test_completed_programs(self, mock_completed_course_runs, mock_get_programs):
        """Verify that completed programs are correctly identified."""
        data = ProgramFactory.create_batch(3)
        mock_get_programs.return_value = data

        program_uuids = []
        course_run_keys = []
        for program in data:
            program_uuids.append(program['uuid'])

            for course in program['courses']:
                for course_run in course['course_runs']:
                    course_run_keys.append(course_run['key'])

        # Verify that no programs are complete.
        meter = ProgramProgressMeter(self.user)
        self.assertEqual(meter.completed_programs, [])

        # Complete all programs.
        self._create_enrollments(*course_run_keys)
        mock_completed_course_runs.return_value = [
            {'course_run_id': course_run_key, 'type': MODES.verified}
            for course_run_key in course_run_keys
        ]

        # Verify that all programs are complete.
        meter = ProgramProgressMeter(self.user)
        self.assertEqual(meter.completed_programs, program_uuids)

    @mock.patch(UTILS_MODULE + '.certificate_api.get_certificates_for_user')
    def test_completed_course_runs(self, mock_get_certificates_for_user, _mock_get_programs):
        """
        Verify that the method can find course run certificates when not mocked out.
        """
        def make_certificate_result(**kwargs):
            """Helper to create dummy results from the certificates API."""
            result = {
                'username': 'dummy-username',
                'course_key': 'dummy-course',
                'type': 'dummy-type',
                'status': 'dummy-status',
                'download_url': 'http://www.example.com/cert.pdf',
                'grade': '0.98',
                'created': '2015-07-31T00:00:00Z',
                'modified': '2015-07-31T00:00:00Z',
            }
            result.update(**kwargs)
            return result

        mock_get_certificates_for_user.return_value = [
            make_certificate_result(status='downloadable', type='verified', course_key='downloadable-course'),
            make_certificate_result(status='generating', type='honor', course_key='generating-course'),
            make_certificate_result(status='unknown', course_key='unknown-course'),
        ]

        meter = ProgramProgressMeter(self.user)
        self.assertEqual(
            meter.completed_course_runs,
            [
                {'course_run_id': 'downloadable-course', 'type': 'verified'},
                {'course_run_id': 'generating-course', 'type': 'honor'},
            ]
        )
        mock_get_certificates_for_user.assert_called_with(self.user.username)


@ddt.ddt
@override_settings(ECOMMERCE_PUBLIC_URL_ROOT=ECOMMERCE_URL_ROOT)
@skip_unless_lms
class TestProgramDataExtender(ModuleStoreTestCase):
    """Tests of the program data extender utility class."""
    maxDiff = None
    sku = 'abc123'
    checkout_path = '/basket'
    instructors = {
        'instructors': [
            {
                'name': 'test-instructor1',
                'organization': 'TextX',
            },
            {
                'name': 'test-instructor2',
                'organization': 'TextX',
            }
        ]
    }

    def setUp(self):
        super(TestProgramDataExtender, self).setUp()

        self.course = ModuleStoreCourseFactory()
        self.course.start = datetime.datetime.now(utc) - datetime.timedelta(days=1)
        self.course.end = datetime.datetime.now(utc) + datetime.timedelta(days=1)
        self.course.instructor_info = self.instructors
        self.course = self.update_course(self.course, self.user.id)

        self.course_run = CourseRunFactory(key=unicode(self.course.id))
        self.catalog_course = CourseFactory(course_runs=[self.course_run])
        self.program = ProgramFactory(courses=[self.catalog_course])

    def _assert_supplemented(self, actual, **kwargs):
        """DRY helper used to verify that program data is extended correctly."""
        self.course_run.update(
            dict(
                {
                    'certificate_url': None,
                    'course_url': reverse('course_root', args=[self.course.id]),
                    'enrollment_open_date': strftime_localized(DEFAULT_ENROLLMENT_START_DATE, 'SHORT_DATE'),
                    'is_course_ended': self.course.end < datetime.datetime.now(utc),
                    'is_enrolled': False,
                    'is_enrollment_open': True,
                    'upgrade_url': None,
                    'advertised_start': None,
                },
                **kwargs
            )
        )

        self.catalog_course['course_runs'] = [self.course_run]
        self.program['courses'] = [self.catalog_course]

        self.assertEqual(actual, self.program)

    @ddt.data(-1, 0, 1)
    def test_is_enrollment_open(self, days_offset):
        """
        Verify that changes to the course run end date do not affect our
        assessment of the course run being open for enrollment.
        """
        self.course.end = datetime.datetime.now(utc) + datetime.timedelta(days=days_offset)
        self.course = self.update_course(self.course, self.user.id)

        data = ProgramDataExtender(self.program, self.user).extend()

        self._assert_supplemented(data)

    @ddt.data(
        (False, None, False),
        (True, MODES.audit, True),
        (True, MODES.verified, False),
    )
    @ddt.unpack
    @mock.patch(UTILS_MODULE + '.CourseMode.mode_for_course')
    def test_student_enrollment_status(self, is_enrolled, enrolled_mode, is_upgrade_required, mock_get_mode):
        """Verify that program data is supplemented with the student's enrollment status."""
        expected_upgrade_url = '{root}/{path}?sku={sku}'.format(
            root=ECOMMERCE_URL_ROOT,
            path=self.checkout_path.strip('/'),
            sku=self.sku,
        )

        update_commerce_config(enabled=True, checkout_page=self.checkout_path)

        mock_mode = mock.Mock()
        mock_mode.sku = self.sku
        mock_get_mode.return_value = mock_mode

        if is_enrolled:
            CourseEnrollmentFactory(user=self.user, course_id=self.course.id, mode=enrolled_mode)

        data = ProgramDataExtender(self.program, self.user).extend()

        self._assert_supplemented(
            data,
            is_enrolled=is_enrolled,
            upgrade_url=expected_upgrade_url if is_upgrade_required else None
        )

    @ddt.data(MODES.audit, MODES.verified)
    def test_inactive_enrollment_no_upgrade(self, enrolled_mode):
        """
        Verify that a student with an inactive enrollment isn't encouraged to upgrade.
        """
        update_commerce_config(enabled=True, checkout_page=self.checkout_path)

        CourseEnrollmentFactory(
            user=self.user,
            course_id=self.course.id,
            mode=enrolled_mode,
            is_active=False,
        )

        data = ProgramDataExtender(self.program, self.user).extend()

        self._assert_supplemented(data)

    @mock.patch(UTILS_MODULE + '.CourseMode.mode_for_course')
    def test_ecommerce_disabled(self, mock_get_mode):
        """
        Verify that the utility can operate when the ecommerce service is disabled.
        """
        update_commerce_config(enabled=False, checkout_page=self.checkout_path)

        mock_mode = mock.Mock()
        mock_mode.sku = self.sku
        mock_get_mode.return_value = mock_mode

        CourseEnrollmentFactory(user=self.user, course_id=self.course.id, mode=MODES.audit)

        data = ProgramDataExtender(self.program, self.user).extend()

        self._assert_supplemented(data, is_enrolled=True, upgrade_url=None)

    @ddt.data(
        (1, 1, False),
        (1, -1, True),
    )
    @ddt.unpack
    def test_course_run_enrollment_status(self, start_offset, end_offset, is_enrollment_open):
        """
        Verify that course run enrollment status is reflected correctly.
        """
        self.course.enrollment_start = datetime.datetime.now(utc) - datetime.timedelta(days=start_offset)
        self.course.enrollment_end = datetime.datetime.now(utc) - datetime.timedelta(days=end_offset)

        self.course = self.update_course(self.course, self.user.id)

        data = ProgramDataExtender(self.program, self.user).extend()

        self._assert_supplemented(
            data,
            is_enrollment_open=is_enrollment_open,
            enrollment_open_date=strftime_localized(self.course.enrollment_start, 'SHORT_DATE'),
        )

    def test_no_enrollment_start_date(self):
        """
        Verify that a closed course run with no explicit enrollment start date
        doesn't cause an error. Regression test for ECOM-4973.
        """
        self.course.enrollment_end = datetime.datetime.now(utc) - datetime.timedelta(days=1)
        self.course = self.update_course(self.course, self.user.id)

        data = ProgramDataExtender(self.program, self.user).extend()

        self._assert_supplemented(
            data,
            is_enrollment_open=False,
        )

    @ddt.data(True, False)
    @mock.patch(UTILS_MODULE + '.certificate_api.certificate_downloadable_status')
    @mock.patch(CERTIFICATES_API_MODULE + '.has_html_certificates_enabled')
    def test_certificate_url_retrieval(self, is_uuid_available, mock_html_certs_enabled, mock_get_cert_data):
        """
        Verify that the student's run mode certificate is included,
        when available.
        """
        test_uuid = uuid.uuid4().hex
        mock_get_cert_data.return_value = {'uuid': test_uuid} if is_uuid_available else {}
        mock_html_certs_enabled.return_value = True

        data = ProgramDataExtender(self.program, self.user).extend()

        expected_url = reverse(
            'certificates:render_cert_by_uuid',
            kwargs={'certificate_uuid': test_uuid}
        ) if is_uuid_available else None

        self._assert_supplemented(data, certificate_url=expected_url)

    def test_instructors_retrieval(self):
        data = ProgramDataExtender(self.program, self.user).extend(include_instructors=True)

        self.program.update(self.instructors['instructors'])
        self.assertEqual(data, self.program)
