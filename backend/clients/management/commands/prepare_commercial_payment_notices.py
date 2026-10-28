"""Prepare PB-NOT payment notices from L2-documented obligations only."""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from clients.models import (
    Client, Collaborator, CommercialPaymentNotice, DocumentedPaymentDue, InternalNotification,
)


NOTICE_WINDOWS = {
    'whatsapp': (7, 3, 1),
    'email': (7,),
    'internal': (7, 3, 1),
}


class Command(BaseCommand):
    help = 'Prepara avisos comerciales idempotentes a partir de vencimientos documentados.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        due_dates = {today + timedelta(days=days): days for days in (1, 3, 7)}
        candidates = list(DocumentedPaymentDue.objects.filter(
            due_date__in=due_dates, client__status='activo',
        ).values_list('pk', 'due_date'))
        created = 0
        skipped = 0
        for due_id, due_date in candidates:
            for channel, offsets in NOTICE_WINDOWS.items():
                days = due_dates.get(due_date)
                if days not in offsets:
                    continue
                was_created = self._prepare_one(due_id, channel, days, today)
                created += int(was_created)
                skipped += int(not was_created)
        self.stdout.write(self.style.SUCCESS(f'Avisos creados: {created}; ya registrados: {skipped}.'))

    @staticmethod
    def _prepare_one(due_id, channel, days, today):
        with transaction.atomic():
            due = DocumentedPaymentDue.objects.select_for_update().select_related(
                'service',
            ).get(pk=due_id)
            client = Client.objects.select_for_update().get(pk=due.client_id)
            if client.status != 'activo' or due.due_date != today + timedelta(days=days):
                return False

            recipient = None
            destination = ''
            error = ''
            if channel == 'internal':
                if client.commercial_responsible_id:
                    recipient = Collaborator.objects.select_for_update().select_related('role').filter(
                        pk=client.commercial_responsible_id, is_active=True, role__is_active=True,
                    ).first()
                if not recipient:
                    error = 'No existe responsable comercial vigente y activo.'
            elif channel == 'email':
                destination = (client.email or '').strip()
                if not destination:
                    error = 'El cliente no tiene correo de contacto.'
                else:
                    try:
                        validate_email(destination)
                    except ValidationError:
                        error = 'El correo de contacto no tiene formato válido.'
            else:
                destination = (client.phone or '').strip()
                if not destination:
                    error = 'El cliente no tiene teléfono de contacto.'

            source_key = f'commercial-due:{due.pk}:{channel}:{days}'
            if channel == 'internal':
                title = 'Seguimiento comercial próximo'
                message = 'Tienes un seguimiento comercial que requiere atención en una fecha próxima.'
            else:
                title = 'Recordatorio de compromiso próximo'
                message = f'Le recordamos que tiene un compromiso documentado próximo, con fecha {due.due_date:%Y-%m-%d}.'

            status = 'fallida' if error else ('disponible' if channel == 'internal' else 'preparada')
            notice, created = CommercialPaymentNotice.objects.get_or_create(
                source_key=source_key,
                defaults=dict(
                due=due, channel=channel, anticipation_days=days, recipient=recipient,
                destination_snapshot=destination, source_key=source_key, status=status,
                title=title, message=message, error_message=error,
                available_at=timezone.now() if channel == 'internal' and not error else None,
                ),
            )
            if not created:
                return False
            if channel == 'internal' and not error:
                InternalNotification.objects.create(
                    recipient=recipient, commercial_due=due,
                    notice_type='commercial_payment_reminder', source_key=source_key,
                    title=title, message=message,
                )
            return bool(notice.pk)
