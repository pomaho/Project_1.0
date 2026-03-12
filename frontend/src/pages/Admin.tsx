import {
  Box,
  Button,
  Chip,
  Container,
  Divider,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  LinearProgress,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import {
  AdminUser,
  AuditLog,
  DownloadLog,
  FullRefreshStatus,
  IndexRunStatus,
  OrphanPreviewStatus,
  ShotAtStatus,
  MissingKeywordItem,
  MissingMetadataSummary,
  CeleryStatus,
  cancelIndex,
  cleanupOrphanPreviews,
  createUser,
  deleteUser,
  fetchAudit,
  fetchDownloads,
  fetchFullRefreshStatus,
  indexStatus,
  listUsers,
  orphanPreviewStatus,
  ReindexStatus,
  reindexStatus,
  previewStatus,
  PreviewStatus,
  shotAtStatus,
  resetShotAt,
  refreshAll,
  restartPreviews,
  updateUser,
  fetchMissingKeywords,
  fetchMissingMetadataSummary,
  fetchCeleryStatus,
  rescanMissingKeywords,
} from "../api/admin";
import { useAuth } from "../auth";
import { withAccessToken } from "../api/client";

const roles = ["admin", "manager", "viewer"] as const;
const roleLabels: Record<(typeof roles)[number], string> = {
  admin: "Администратор",
  manager: "Менеджер",
  viewer: "Наблюдатель",
};

export default function AdminPage() {
  const [tab, setTab] = useState(0);
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [downloads, setDownloads] = useState<DownloadLog[]>([]);
  const [downloadsPage, setDownloadsPage] = useState(0);
  const downloadsLimit = 50;
  const [status, setStatus] = useState<{ files: number; run?: IndexRunStatus | null } | null>(
    null
  );
  const [fullRefresh, setFullRefresh] = useState<FullRefreshStatus | null>(null);
  const [preview, setPreview] = useState<PreviewStatus | null>(null);
  const [orphans, setOrphans] = useState<OrphanPreviewStatus | null>(null);
  const [reindex, setReindex] = useState<ReindexStatus | null>(null);
  const [shotAt, setShotAt] = useState<ShotAtStatus | null>(null);
  const [missingKeywords, setMissingKeywords] = useState<MissingKeywordItem[]>([]);
  const [missingMetaSummary, setMissingMetaSummary] = useState<MissingMetadataSummary | null>(null);
  const [celery, setCelery] = useState<CeleryStatus | null>(null);
  const [missingKeywordsTotal, setMissingKeywordsTotal] = useState(0);
  const [missingKeywordsPage, setMissingKeywordsPage] = useState(0);
  const missingKeywordsLimit = 50;
  const [missingKeywordsBaseline, setMissingKeywordsBaseline] = useState<number | null>(null);
  const [missingKeywordsQueued, setMissingKeywordsQueued] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "viewer" });
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [restartPreviewBusy, setRestartPreviewBusy] = useState(false);
  const [shotAtBusy, setShotAtBusy] = useState(false);
  const [orphanBusy, setOrphanBusy] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [missingKeywordsBusy, setMissingKeywordsBusy] = useState(false);
  const [missingKeywordsRescanBusy, setMissingKeywordsRescanBusy] = useState(false);

  useEffect(() => {
    listUsers().then(setUsers).catch(() => setUsers([]));
    fetchAudit().then(setAudit).catch(() => setAudit([]));
    fetchDownloads(downloadsLimit, downloadsPage * downloadsLimit)
      .then(setDownloads)
      .catch(() => setDownloads([]));
    indexStatus().then(setStatus).catch(() => setStatus(null));
    fetchFullRefreshStatus().then(setFullRefresh).catch(() => setFullRefresh(null));
    previewStatus().then(setPreview).catch(() => setPreview(null));
    orphanPreviewStatus().then(setOrphans).catch(() => setOrphans(null));
    reindexStatus().then(setReindex).catch(() => setReindex(null));
    shotAtStatus().then(setShotAt).catch(() => setShotAt(null));
    fetchMissingMetadataSummary().then(setMissingMetaSummary).catch(() => setMissingMetaSummary(null));
    fetchCeleryStatus().then(setCelery).catch(() => setCelery(null));
    if (tab === 3) {
      fetchMissingKeywords(missingKeywordsLimit, missingKeywordsPage * missingKeywordsLimit)
        .then((data) => {
          setMissingKeywords(data.items);
          setMissingKeywordsTotal(data.total);
        })
        .catch(() => {
          setMissingKeywords([]);
          setMissingKeywordsTotal(0);
        });
    }
    const interval = window.setInterval(() => {
      if (document.hidden) return;
      indexStatus().then(setStatus).catch(() => setStatus(null));
      fetchFullRefreshStatus().then(setFullRefresh).catch(() => setFullRefresh(null));
      previewStatus().then(setPreview).catch(() => setPreview(null));
      orphanPreviewStatus().then(setOrphans).catch(() => setOrphans(null));
      reindexStatus().then(setReindex).catch(() => setReindex(null));
      shotAtStatus().then(setShotAt).catch(() => setShotAt(null));
      fetchMissingMetadataSummary().then(setMissingMetaSummary).catch(() => setMissingMetaSummary(null));
      fetchCeleryStatus().then(setCelery).catch(() => setCelery(null));
      if (tab === 2) {
        fetchDownloads(downloadsLimit, downloadsPage * downloadsLimit)
          .then(setDownloads)
          .catch(() => setDownloads([]));
      }
      if (tab === 3) {
        fetchMissingKeywords(missingKeywordsLimit, missingKeywordsPage * missingKeywordsLimit)
          .then((data) => {
            setMissingKeywords(data.items);
            setMissingKeywordsTotal(data.total);
          })
          .catch(() => {
            setMissingKeywords([]);
            setMissingKeywordsTotal(0);
          });
      }
    }, 15000);
    return () => window.clearInterval(interval);
  }, [tab, downloadsPage, missingKeywordsPage]);

  const run = status?.run ?? null;
  const previewProgress = Math.round(((preview?.progress ?? 0) * 100) || 0);
  const orphanProgress = orphans?.total_orphans
    ? Math.min(
        100,
        Math.round(((orphans?.deleted ?? 0) / orphans.total_orphans) * 100)
      )
    : 0;
  const shotAtProgress =
    shotAt && shotAt.total > 0
      ? Math.min(100, Math.round((shotAt.scanned / shotAt.total) * 100))
      : 0;
  const formatTaskBreakdown = (items: { task: string; count: number }[] | undefined) =>
    items && items.length > 0 ? items.map((item) => `${item.task}: ${item.count}`).join(" | ") : "-";
  const queueLengthsText = celery?.queue_lengths
    ? Object.entries(celery.queue_lengths)
        .filter(([, count]) => count > 0)
        .map(([name, count]) => `${name}: ${count}`)
        .join(" | ")
    : "-";
  const metadataSearchQueue =
    (celery?.queue_head ?? []).filter((item) =>
      ["extract_metadata", "upsert_search_doc", "flush_upsert_search_docs"].includes(item.task)
    );

  const handleCreateUser = async () => {
    const payload = { ...form };
    if (!payload.email || !payload.password) return;
    const created = await createUser(payload);
    setUsers((prev) => [created, ...prev]);
    setForm({ name: "", email: "", password: "", role: "viewer" });
  };

  const handleRoleChange = async (user: AdminUser, role: string) => {
    const updated = await updateUser(user.id, { role });
    setUsers((prev) => prev.map((item) => (item.id === user.id ? updated : item)));
  };

  const handleToggleActive = async (user: AdminUser) => {
    const updated = await updateUser(user.id, { is_active: !user.is_active });
    setUsers((prev) => prev.map((item) => (item.id === user.id ? updated : item)));
  };

  const handleDelete = async (user: AdminUser) => {
    await deleteUser(user.id);
    setUsers((prev) => prev.filter((item) => item.id !== user.id));
  };

  const handleResetPassword = async (user: AdminUser) => {
    const next = window.prompt(`Новый пароль для ${user.email}`);
    if (!next) return;
    await updateUser(user.id, { password: next });
  };

  const auditRows = useMemo(
    () => audit.map((row) => ({ ...row, metaJson: JSON.stringify(row.meta) })),
    [audit]
  );

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Администрирование
        </Typography>
        <Button variant="text" href="/">
          На главную
        </Button>
      </Stack>
      <Stack direction="row" justifyContent="flex-end" sx={{ mb: 2, mt: -1 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {user?.name || user?.email || "Пользователь"}
        </Typography>
      </Stack>
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
          <Typography variant="body1">Файлов в индексе: {status?.files ?? "-"}</Typography>
          <Button
            variant="contained"
            onClick={async () => {
              setRefreshBusy(true);
              try {
                await refreshAll();
              } finally {
                setRefreshBusy(false);
              }
            }}
            disabled={refreshBusy}
          >
            Обновить базу полностью
          </Button>
          <Button
            variant="outlined"
            color="warning"
            onClick={async () => {
              setCancelBusy(true);
              try {
                await cancelIndex();
              } finally {
                setCancelBusy(false);
              }
            }}
            disabled={cancelBusy || run?.status !== "running"}
          >
            Остановить скан
          </Button>
        </Stack>
        <Box sx={{ mt: 1 }}>
          <Button
            variant="text"
            color="warning"
            onClick={async () => {
              setShotAtBusy(true);
              try {
                await resetShotAt();
                await shotAtStatus().then(setShotAt).catch(() => setShotAt(null));
              } finally {
                setShotAtBusy(false);
              }
            }}
            disabled={shotAtBusy}
          >
            Сбросить прогресс
          </Button>
        </Box>
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Полное обновление: {fullRefresh?.status ?? "-"} | Этап: {fullRefresh?.stage_detail ?? "-"}
          </Typography>
          <LinearProgress
            variant={
              fullRefresh?.status === "running" && typeof fullRefresh?.progress !== "number"
                ? "indeterminate"
                : "determinate"
            }
            value={
              typeof fullRefresh?.progress === "number"
                ? fullRefresh.progress
                : fullRefresh?.status === "completed"
                  ? 100
                  : 0
            }
            sx={{ height: 8, borderRadius: 999 }}
          />
        </Box>
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2">
            Реиндекс: {reindex?.status ?? "-"} | Обработано: {reindex?.count ?? "-"}
          </Typography>
        <Box sx={{ mt: 1 }}>
          <Typography variant="body2">
            Отсутствуют метаданные: ключевые слова {missingMetaSummary?.missing_keywords ?? "-"} | заголовок/описание {missingMetaSummary?.missing_text ?? "-"} | дата съемки {missingMetaSummary?.missing_shot_at ?? "-"}
          </Typography>
        </Box>
        </Box>
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            Очередь метаданных и поиска:{" "}
            {formatTaskBreakdown(metadataSearchQueue.length ? metadataSearchQueue : undefined)}
          </Typography>
          <Typography variant="caption" sx={{ display: "block", mt: 0.5 }}>
            Очереди Redis: {queueLengthsText}
          </Typography>
          <Typography variant="caption" sx={{ display: "block", mt: 0.5 }}>
            Источник выборки: {formatTaskBreakdown(celery?.queue_sample_sources)}
          </Typography>
        </Box>
        <Box sx={{ mt: 2 }}>
          <Stack
            direction={{ xs: "column", md: "row" }}
            spacing={1}
            alignItems={{ xs: "flex-start", md: "center" }}
          >
            <Typography variant="body2">
              Очередь Celery: {celery?.status ?? "-"} | Задач: {celery?.queue_length ?? "-"} | Активно:{" "}
              {celery?.active_total ?? "-"} | В резерве: {celery?.reserved_total ?? "-"} |
              Запланировано: {celery?.scheduled_total ?? "-"}
            </Typography>
            {celery?.queue_head_duplicate_overflows?.length ? (
              <Chip
                size="small"
                color="warning"
                label={`Дубли в начале очереди: ${formatTaskBreakdown(
                  celery.queue_head_duplicate_overflows
                )}`}
              />
            ) : null}
            {celery?.active_duplicate_overflows?.length ? (
              <Chip
                size="small"
                color="warning"
                label={`Дубли в активных задачах: ${formatTaskBreakdown(
                  celery.active_duplicate_overflows
                )}`}
              />
            ) : null}
          </Stack>
          <Typography variant="caption" sx={{ display: "block", mt: 1 }}>
            Активные задачи: {formatTaskBreakdown(celery?.active)}
          </Typography>
          <Typography variant="caption" sx={{ display: "block", mt: 0.5 }}>
            Резерв по задачам: {formatTaskBreakdown(celery?.reserved)}
          </Typography>
          <Typography variant="caption" sx={{ display: "block", mt: 0.5 }}>
            Начало очереди ({celery?.queue_sample_size ?? 0} в выборке):{" "}
            {formatTaskBreakdown(celery?.queue_head)}
          </Typography>
        </Box>
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Даты съемки: {shotAt?.status ?? "-"} | Обработано: {shotAt?.scanned ?? "-"} /{" "}
            {shotAt?.total ?? "-"} | Обновлено: {shotAt?.updated ?? "-"}
          </Typography>
          <LinearProgress
            variant={shotAt?.total ? "determinate" : "determinate"}
            value={shotAtProgress}
            sx={{ height: 8, borderRadius: 999 }}
          />
        </Box>
        {run && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Статус: {run.status} | Просканировано: {run.scanned} | Создано: {run.created} |
              Обновлено: {run.updated} | Восстановлено: {run.restored} | Удалено: {run.deleted}
            </Typography>
            {run.status === "running" ? (
              <LinearProgress sx={{ height: 8, borderRadius: 999 }} />
            ) : (
              <LinearProgress
                variant="determinate"
                value={100}
                color={run.status === "failed" ? "error" : "success"}
                sx={{ height: 8, borderRadius: 999 }}
              />
            )}
            {run.finished_at && (
              <Typography variant="caption" sx={{ display: "block", mt: 1 }}>
                Завершено: {new Date(run.finished_at).toLocaleString()}
              </Typography>
            )}
            {run.error && (
              <Typography variant="caption" color="error" sx={{ display: "block" }}>
                Ошибка: {run.error}
              </Typography>
            )}
          </Box>
        )}
      </Paper>
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
          <Typography variant="body1">
            Превью: {preview?.total_previews ?? "-"} | Файлов: {preview?.total_files ?? "-"} |
            Без превью: {preview?.missing_previews ?? "-"}
          </Typography>
          <Button
            variant="contained"
            color="warning"
            onClick={async () => {
              setRestartPreviewBusy(true);
              try {
                await restartPreviews();
              } finally {
                setRestartPreviewBusy(false);
              }
            }}
            disabled={restartPreviewBusy}
          >
            Перезапустить генерацию превью
          </Button>
        </Stack>
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Прогресс: {previewProgress}% | Раунд {preview?.round ?? 0} из{" "}
            {preview?.max_rounds ?? 0} | Статус: {preview?.status ?? "-"}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={previewProgress}
            sx={{ height: 8, borderRadius: 999 }}
          />
        </Box>
        <Box sx={{ mt: 2 }}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
            <Typography variant="body2">
              Сироты: {orphans?.total_orphans ?? "-"} | Удалено: {orphans?.deleted ?? "-"} |
              Обработано: {orphans?.processed ?? "-"} | Статус: {orphans?.status ?? "-"}
            </Typography>
            <Button
              variant="outlined"
              color="warning"
              onClick={async () => {
                setOrphanBusy(true);
                try {
                  await cleanupOrphanPreviews();
                } finally {
                  setOrphanBusy(false);
                }
              }}
              disabled={orphanBusy}
            >
              Очистить сироты
            </Button>
          </Stack>
          <Box sx={{ mt: 1 }}>
            <LinearProgress
              variant="determinate"
              value={orphanProgress}
              sx={{ height: 8, borderRadius: 999 }}
            />
          </Box>
        </Box>
      </Paper>
      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 2 }}>
        <Tab label="Пользователи" />
        <Tab label="Аудит" />
        <Tab label="Скачивания" />
        <Tab label="Ключевые слова" />
      </Tabs>
      {tab === 2 ? (
        <Paper>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Время</TableCell>
                <TableCell>Пользователь</TableCell>
                <TableCell>IP</TableCell>
                <TableCell>Превью</TableCell>
                <TableCell>Файл</TableCell>
                <TableCell>Путь</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {downloads.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{new Date(row.created_at).toLocaleString()}</TableCell>
                  <TableCell>{row.user_email}</TableCell>
                  <TableCell>{row.ip}</TableCell>
                  <TableCell>
                    <Box
                      component="img"
                      src={withAccessToken(`/api/files/${row.file_id}/preview?size=thumb`)}
                      alt={row.filename || row.file_id}
                      sx={{ width: 56, height: 40, objectFit: "contain", borderRadius: 1 }}
                    />
                  </TableCell>
                  <TableCell>{row.filename || row.file_id}</TableCell>
                  <TableCell>{row.original_key}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ p: 2, justifyContent: "flex-end" }}>
            <Button
              size="small"
              variant="outlined"
              disabled={downloadsPage === 0}
              onClick={() => setDownloadsPage((prev) => Math.max(0, prev - 1))}
            >
              Назад
            </Button>
            <Typography variant="body2">
              Страница {downloadsPage + 1}
            </Typography>
            <Button
              size="small"
              variant="outlined"
              disabled={downloads.length < downloadsLimit}
              onClick={() => setDownloadsPage((prev) => prev + 1)}
            >
              Вперед
            </Button>
          </Stack>
        </Paper>
      ) : tab === 3 ? (
        <Paper>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={2}
            alignItems="center"
            sx={{ p: 2 }}
          >
            <Typography variant="body2">
              Без ключевых слов: {missingKeywordsTotal}
            </Typography>
            {missingKeywordsBaseline !== null && (
              <Typography variant="body2">
                Осталось: {missingKeywordsTotal} / {missingKeywordsBaseline}
              </Typography>
            )}
            {missingKeywordsQueued !== null && (
              <Typography variant="body2">В очереди: {missingKeywordsQueued}</Typography>
            )}
            <Button
              variant="outlined"
              onClick={async () => {
                setMissingKeywordsBusy(true);
                try {
                  const data = await fetchMissingKeywords(
                    missingKeywordsLimit,
                    missingKeywordsPage * missingKeywordsLimit
                  );
                  setMissingKeywords(data.items);
                  setMissingKeywordsTotal(data.total);
                } finally {
                  setMissingKeywordsBusy(false);
                }
              }}
              disabled={missingKeywordsBusy}
            >
              Обновить список
            </Button>
            <Button
              variant="contained"
              onClick={async () => {
                setMissingKeywordsRescanBusy(true);
                try {
                  if (missingKeywordsBaseline === null) {
                    setMissingKeywordsBaseline(missingKeywordsTotal);
                  }
                  const result = await rescanMissingKeywords();
                  if (typeof result.queued === "number") {
                    setMissingKeywordsQueued(result.queued);
                  }
                } finally {
                  setMissingKeywordsRescanBusy(false);
                }
              }}
              disabled={missingKeywordsRescanBusy}
            >
              Пересканировать файлы без ключевых слов
            </Button>
          </Stack>
          {missingKeywordsBaseline !== null && (
            <Box sx={{ px: 2, pb: 2 }}>
              <LinearProgress
                variant="determinate"
                value={
                  missingKeywordsBaseline === 0
                    ? 100
                    : Math.min(
                        100,
                        Math.round(
                          ((missingKeywordsBaseline - missingKeywordsTotal) /
                            missingKeywordsBaseline) *
                            100
                        )
                      )
                }
                sx={{ height: 8, borderRadius: 999 }}
              />
            </Box>
          )}
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Превью</TableCell>
                <TableCell>Файл</TableCell>
                <TableCell>Путь</TableCell>
                <TableCell>Дата изменения</TableCell>
                <TableCell align="right">Размер (KB)</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {missingKeywords.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <Box
                      component="img"
                      src={withAccessToken(`/api/files/${row.id}/preview?size=thumb`)}
                      alt={row.filename || row.id}
                      sx={{ width: 56, height: 40, objectFit: "contain", borderRadius: 1 }}
                    />
                  </TableCell>
                  <TableCell>{row.filename}</TableCell>
                  <TableCell>{row.original_key}</TableCell>
                  <TableCell>{new Date(row.mtime).toLocaleString()}</TableCell>
                  <TableCell align="right">{Math.round(row.size_bytes / 1024)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Stack
            direction="row"
            spacing={2}
            alignItems="center"
            sx={{ p: 2, justifyContent: "flex-end" }}
          >
            <Button
              size="small"
              variant="outlined"
              disabled={missingKeywordsPage === 0}
              onClick={() => setMissingKeywordsPage((prev) => Math.max(0, prev - 1))}
            >
              Назад
            </Button>
            <Typography variant="body2">
              Страница {missingKeywordsPage + 1}
            </Typography>
            <Button
              size="small"
              variant="outlined"
              disabled={(missingKeywordsPage + 1) * missingKeywordsLimit >= missingKeywordsTotal}
              onClick={() => setMissingKeywordsPage((prev) => prev + 1)}
            >
              Вперед
            </Button>
          </Stack>
        </Paper>
      ) : tab === 0 ? (
        <Box>
          <Paper sx={{ p: 2, mb: 3 }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="center">
              <TextField
                label="Имя"
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              />
              <TextField
                label="Почта"
                value={form.email}
                onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
              />
              <TextField
                label="Пароль"
                type="password"
                value={form.password}
                onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
              />
              <FormControl size="small">
                <InputLabel>Роль</InputLabel>
                <Select
                  label="Роль"
                  value={form.role}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, role: event.target.value }))
                  }
                >
                  {roles.map((role) => (
                    <MenuItem key={role} value={role}>
                      {roleLabels[role]}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Button variant="contained" onClick={handleCreateUser}>
                Добавить
              </Button>
            </Stack>
          </Paper>
          <Paper>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Имя</TableCell>
                  <TableCell>Почта</TableCell>
                  <TableCell>Роль</TableCell>
                  <TableCell>Активен</TableCell>
                  <TableCell align="right">Действия</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>{user.name || user.email}</TableCell>
                    <TableCell>{user.email}</TableCell>
                    <TableCell>
                      <Select
                        size="small"
                        value={user.role}
                        onChange={(event) => handleRoleChange(user, event.target.value)}
                      >
                        {roles.map((role) => (
                          <MenuItem key={role} value={role}>
                            {roleLabels[role]}
                          </MenuItem>
                        ))}
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Button size="small" onClick={() => handleToggleActive(user)}>
                        {user.is_active ? "Отключить" : "Включить"}
                      </Button>
                    </TableCell>
                    <TableCell align="right">
                      <Button size="small" onClick={() => handleResetPassword(user)}>
                        Сбросить пароль
                      </Button>
                      <Button color="error" size="small" onClick={() => handleDelete(user)}>
                        Удалить
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        </Box>
      ) : (
        <Paper>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Время</TableCell>
                <TableCell>Пользователь</TableCell>
                <TableCell>Действие</TableCell>
                <TableCell>Метаданные</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {auditRows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{new Date(row.created_at).toLocaleString()}</TableCell>
                  <TableCell>{row.user_id}</TableCell>
                  <TableCell>{row.action}</TableCell>
                  <TableCell>{row.metaJson}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
      <Divider sx={{ mt: 4 }} />
    </Container>
  );
}

