export function projectCancellationStatus(cancellations = [], resumptions = [], now = Date.now()) {
  const effective = cancellations.flatMap((cancellation) => cancellation.events
    .filter((event) => event.event_type === "efectiva" && event.effective_at)
    .map((event) => ({ cancellation, event })))
    .filter(({ event }) => new Date(event.effective_at).getTime() <= now)
    .sort((left, right) => (
      new Date(right.event.effective_at).getTime() - new Date(left.event.effective_at).getTime()
      || Number(right.event.id || 0) - Number(left.event.id || 0)
    ));

  const latest = effective[0];
  if (!latest) return { current: null, resumed: null };

  const resumption = resumptions.find((item) => (
    Number(item.cancellation_id) === Number(latest.cancellation.id)
    && item.events.some((event) => (
      event.event_type === "reanudacion_registrada"
      && new Date(event.occurred_at).getTime() > new Date(latest.event.occurred_at).getTime()
    ))
  ));

  return resumption
    ? { current: null, resumed: { ...latest, resumption } }
    : { current: latest, resumed: null };
}
