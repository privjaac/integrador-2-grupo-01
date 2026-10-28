package elisa.notifications;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.LinkedHashSet;
import java.util.Set;

/** Classifies approved task deadline rules and returns notification drafts. */
public final class TaskDeadlineProcessor {
    private static final long REMINDER_WINDOW_MILLIS = Duration.ofHours(24).toMillis();

    private TaskDeadlineProcessor() { }

    public static void main(String[] args) throws Exception {
        try (BufferedReader input = new BufferedReader(
                new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
            String line;
            while ((line = input.readLine()) != null) {
                if (line.isBlank()) continue;
                process(line);
            }
        }
    }

    private static void process(String line) {
        String[] fields = line.split("\\t", -1);
        if (fields.length != 7) throw new IllegalArgumentException("Invalid candidate record");

        long taskId = Long.parseLong(fields[0]);
        String status = decode(fields[1]);
        String title = decode(fields[2]);
        long dueAt = Long.parseLong(fields[3]);
        long now = Long.parseLong(fields[4]);
        long responsibleId = Long.parseLong(fields[5]);
        long creatorId = Long.parseLong(fields[6]);

        if ("Finalizada".equals(status) || "Cancelada".equals(status)) {
            System.out.printf("S\t%d\tterminal_status%n", taskId);
            return;
        }

        if (dueAt > now && dueAt - now <= REMINDER_WINDOW_MILLIS) {
            if (responsibleId > 0) {
                emit(taskId, "tarea_recordatorio", responsibleId,
                        "Tarea próxima a vencer",
                        "Recordatorio: La tarea " + title + " vence pronto.");
            }
            return;
        }

        if (dueAt <= now) {
            Set<Long> recipients = new LinkedHashSet<>();
            if (responsibleId > 0) recipients.add(responsibleId);
            if (creatorId > 0) recipients.add(creatorId);
            for (long recipientId : recipients) {
                emit(taskId, "tarea_vencida", recipientId,
                        "Tarea vencida", "Alerta: La tarea " + title + " ha vencido.");
            }
        }
    }

    private static void emit(long taskId, String kind, long recipientId,
                             String title, String message) {
        System.out.printf("N\t%d\t%s\t%d\t%s\t%s%n",
                taskId, kind, recipientId, encode(title), encode(message));
    }

    private static String encode(String value) {
        return Base64.getUrlEncoder().withoutPadding()
                .encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    private static String decode(String value) {
        return new String(Base64.getUrlDecoder().decode(value), StandardCharsets.UTF_8);
    }
}
