import {
  Box,
  Button,
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
  IndexRunStatus,
  createUser,
  deleteUser,
  fetchAudit,
  indexStatus,
  listUsers,
  refreshAll,
  updateUser,
} from "../api/admin";

const roles = ["admin", "editor", "viewer"] as const;

export default function AdminPage() {
  const [tab, setTab] = useState(0);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [status, setStatus] = useState<{ files: number; run?: IndexRunStatus | null } | null>(
    null
  );
  const [form, setForm] = useState({ email: "", password: "", role: "viewer" });
  const [refreshBusy, setRefreshBusy] = useState(false);

  useEffect(() => {
    listUsers().then(setUsers).catch(() => setUsers([]));
    fetchAudit().then(setAudit).catch(() => setAudit([]));
    indexStatus().then(setStatus).catch(() => setStatus(null));
    const interval = window.setInterval(() => {
      indexStatus().then(setStatus).catch(() => setStatus(null));
    }, 5000);
    return () => window.clearInterval(interval);
  }, []);

  const run = status?.run ?? null;

  const handleCreateUser = async () => {
    const payload = { ...form };
    if (!payload.email || !payload.password) return;
    const created = await createUser(payload);
    setUsers((prev) => [created, ...prev]);
    setForm({ email: "", password: "", role: "viewer" });
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
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
          <Typography variant="body1">Файлов в индексе: {status?.files ?? "—"}</Typography>
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
            Обновить базу
          </Button>
        </Stack>
        {run && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Статус: {run.status} • Просканировано: {run.scanned} • Создано: {run.created} •
              Обновлено: {run.updated} • Восстановлено: {run.restored} • Удалено: {run.deleted}
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
      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 2 }}>
        <Tab label="Пользователи" />
        <Tab label="Аудит" />
      </Tabs>
      {tab === 0 ? (
        <Box>
          <Paper sx={{ p: 2, mb: 3 }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="center">
              <TextField
                label="Email"
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
                      {role}
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
                  <TableCell>Email</TableCell>
                  <TableCell>Роль</TableCell>
                  <TableCell>Активен</TableCell>
                  <TableCell align="right">Действия</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>{user.email}</TableCell>
                    <TableCell>
                      <Select
                        size="small"
                        value={user.role}
                        onChange={(event) => handleRoleChange(user, event.target.value)}
                      >
                        {roles.map((role) => (
                          <MenuItem key={role} value={role}>
                            {role}
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
                <TableCell>Meta</TableCell>
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
