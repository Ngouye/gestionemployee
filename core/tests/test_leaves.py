from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from core.models import Notification
from leaves import services
from leaves.models import LeaveRequest, LeaveType, PublicHoliday

from .base import DemoDataTestCase


def next_monday(after=None):
    day = (after or date.today()) + timedelta(days=60)
    return day + timedelta(days=(7 - day.weekday()) % 7)


class WorkingDaysTests(DemoDataTestCase):
    def setUp(self):
        PublicHoliday.objects.all().delete()

    def test_weekends_are_excluded(self):
        monday = next_monday()
        self.assertEqual(services.working_days(monday, monday + timedelta(days=6)), Decimal(5))

    def test_holidays_are_excluded(self):
        monday = next_monday()
        PublicHoliday.objects.create(name='Férié test', date=monday + timedelta(days=2))
        self.assertEqual(services.working_days(monday, monday + timedelta(days=4)), Decimal(4))

    def test_recurring_holiday(self):
        PublicHoliday.objects.create(name='Fête du Travail', date=date(2000, 5, 1), is_recurring=True)
        may_first = next(date(year, 5, 1) for year in range(2030, 2040) if date(year, 5, 1).weekday() < 5)
        self.assertEqual(services.working_days(may_first, may_first), Decimal(0))

    def test_half_day(self):
        monday = next_monday()
        self.assertEqual(services.working_days(monday, monday, half_day=True), Decimal('0.5'))


class LeaveWorkflowTests(DemoDataTestCase):
    def setUp(self):
        self.annual = LeaveType.objects.get(code='CA')
        self.employee = self.employee_user.employee
        self.start = next_monday()

    def request_leave(self, start, end, leave_type=None):
        self.login(self.employee_user)
        return self.client.post(reverse('leaves:create'), {
            'leave_type': (leave_type or self.annual).pk, 'start_date': start.isoformat(),
            'end_date': end.isoformat(), 'reason': 'Test'})

    def test_request_notifies_manager_and_manager_approves(self):
        response = self.request_leave(self.start, self.start + timedelta(days=1))
        self.assertRedirects(response, reverse('leaves:my_leaves'), fetch_redirect_response=False)
        leave = LeaveRequest.objects.filter(employee=self.employee).latest('created_at')
        self.assertEqual(leave.days, Decimal(2))
        self.assertTrue(Notification.objects.filter(user=self.manager, title__contains='congé').exists())

        self.login(self.manager)
        self.client.post(reverse('leaves:decide', args=[leave.pk]), {'decision': 'approve'})
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(leave.reviewed_by, self.manager)
        self.assertTrue(Notification.objects.filter(user=self.employee_user, title__contains='approuvée').exists())

    def test_reject_requires_comment(self):
        self.request_leave(self.start, self.start)
        leave = LeaveRequest.objects.filter(employee=self.employee).latest('created_at')
        self.login(self.manager)
        self.client.post(reverse('leaves:decide', args=[leave.pk]), {'decision': 'reject'})
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)

    def test_employee_cannot_approve_own_request(self):
        self.request_leave(self.start, self.start)
        leave = LeaveRequest.objects.filter(employee=self.employee).latest('created_at')
        response = self.client.post(reverse('leaves:decide', args=[leave.pk]), {'decision': 'approve'})
        self.assertEqual(response.status_code, 403)

    def test_insufficient_balance_is_refused(self):
        response = self.request_leave(self.start, self.start + timedelta(days=60))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Solde insuffisant')

    def test_overlap_is_refused(self):
        self.request_leave(self.start, self.start + timedelta(days=1))
        response = self.request_leave(self.start + timedelta(days=1), self.start + timedelta(days=2))
        self.assertContains(response, 'existe déjà')

    def test_attachment_required_for_sick_leave(self):
        response = self.request_leave(self.start, self.start, LeaveType.objects.get(code='MAL'))
        self.assertContains(response, 'justificatif est obligatoire')

    def test_allocate_year_with_carry_over(self):
        year = date.today().year + 1
        created = services.allocate_year(year)
        self.assertGreater(created, 0)
        balance = services.get_balance(self.employee, self.annual, year)
        self.assertEqual(balance.allocated, self.annual.annual_allowance)
        self.assertLessEqual(balance.carried_over, self.annual.max_carry_over)
