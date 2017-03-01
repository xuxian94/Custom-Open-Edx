"""
Test Help links in LMS
"""
import json


from common.test.acceptance.tests.lms.test_lms_instructor_dashboard import BaseInstructorDashboardTest
from common.test.acceptance.pages.lms.instructor_dashboard import InstructorDashboardPage
from common.test.acceptance.tests.studio.base_studio_test import ContainerBase
from common.test.acceptance.fixtures import LMS_BASE_URL
from common.test.acceptance.fixtures.course import CourseFixture

from common.test.acceptance.tests.helpers import (
    assert_link,
    assert_opened_help_link_is_correct
)


class TestCohortHelp(ContainerBase):
    """
    Tests help links in Cohort page
    """
    def setUp(self, is_staff=True):
        super(TestCohortHelp, self).setUp(is_staff=is_staff)
        self.enable_cohorting(self.course_fixture)
        self.instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course_id)
        self.instructor_dashboard_page.visit()
        self.cohort_management = self.instructor_dashboard_page.select_cohort_management()

    def get_url_with_changed_domain(self, url):
        """
        Replaces .org with .io in the url
        Arguments:
            url (str): The url to perform replace operation on.
        Returns:
        str: The updated url
        """
        return url.replace('.org/', '.io/')

    def verify_help_link(self, href):
        """
        Verifies that help link is correct
        Arguments:
            href (str): Help url
        """
        expected_link = {
            'href': href,
            'text': 'What does this mean?'
        }
        actual_link = self.cohort_management.get_cohort_help_element_and_click_help()

        assert_link(self, expected_link, actual_link)
        assert_opened_help_link_is_correct(self, self.get_url_with_changed_domain(href))

    def test_manual_cohort_help(self):
        """
        Scenario: Help in 'What does it mean?' is correct when we create cohort manually.
        Given that I am at 'Cohort' tab of LMS instructor dashboard
        And I check 'Enable Cohorts'
        And I add cohort name it, choose Manual for Cohort Assignment Method and
        No content group for Associated Content Group and save the cohort
        Then you see the UI text "Learners are added to this cohort only when..."
        followed by "What does this mean" link.
        And I click "What does this mean" link then help link should end with
        course_features/cohorts/cohort_config.html#assign-learners-to-cohorts-manually
        """
        self.cohort_management.add_cohort('cohort_name')

        href = 'http://edx.readthedocs.org/projects/edx-partner-course-staff/en/latest/' \
               'course_features/cohorts/cohort_config.html#assign-learners-to-cohorts-manually'

        self.verify_help_link(href)

    def test_automatic_cohort_help(self):
        """
        Scenario: Help in 'What does it mean?' is correct when we create cohort automatically.
        Given that I am at 'Cohort' tab of LMS instructor dashboard
        And I check 'Enable Cohorts'
        And I add cohort name it, choose Automatic for Cohort Assignment Method and
        No content group for Associated Content Group and save the cohort
        Then you see the UI text "Learners are added to this cohort automatically"
        followed by "What does this mean" link.
        And I click "What does this mean" link then help link should end with
        course_features/cohorts/cohorts_overview.html#all-automated-assignment
        """

        self.cohort_management.add_cohort('cohort_name', assignment_type='random')

        href = 'http://edx.readthedocs.org/projects/edx-partner-course-staff/en/latest/' \
               'course_features/cohorts/cohorts_overview.html#all-automated-assignment'

        self.verify_help_link(href)

    def enable_cohorting(self, course_fixture):
        """
        Enables cohorting for the current course.
        """
        url = LMS_BASE_URL + "/courses/" + course_fixture._course_key + '/cohorts/settings'  # pylint: disable=protected-access
        data = json.dumps({'is_cohorted': True})
        response = course_fixture.session.patch(url, data=data, headers=course_fixture.headers)
        self.assertTrue(response.ok, "Failed to enable cohorts")


class InstructorDashboardHelp(BaseInstructorDashboardTest):
    """
    Tests opening help from the general Help button in the instructor dashboard.
    """

    def setUp(self):
        super(InstructorDashboardHelp, self).setUp()
        self.course_fixture = CourseFixture(**self.course_info).install()
        self.log_in_as_instructor()
        self.instructor_dashboard_page = self.visit_instructor_dashboard()

    def test_instructor_dashboard_help(self):
        """
        Scenario: Help button opens staff help
        Given that I am viewing the Instructor Dashboard
        When I click "Help"
        Then I see help about the instructor dashboard in a new tab
        """
        href = 'http://edx.readthedocs.io/projects/edx-guide-for-students/en/latest/SFD_instructor_dash_help.html'
        self.instructor_dashboard_page.click_help()
        assert_opened_help_link_is_correct(self, href)
