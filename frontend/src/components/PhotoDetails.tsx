import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import CloudDownloadIcon from "@mui/icons-material/CloudDownload";
import { useEffect, useMemo, useState } from "react";
import { withAccessToken } from "../api/client";
import { getDownloadToken, getFile, updateKeywords } from "../api/files";
import { extractTerms, highlightText } from "../utils/highlight";

export default function PhotoDetails({
  fileId,
  open,
  onClose,
  query,
}: {
  fileId: string | null;
  open: boolean;
  onClose: () => void;
  query: string;
}) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [keywords, setKeywords] = useState<string[]>([]);
  const [file, setFile] = useState<Awaited<ReturnType<typeof getFile>> | null>(null);

  useEffect(() => {
    if (!open || !fileId) return;
    setLoading(true);
    setError("");
    setFile(null);
    setKeywords([]);
    setKeywordInput("");
    getFile(fileId)
      .then((data) => {
        setFile(data);
        setKeywords(data.keywords);
      })
      .catch(() => setError("Не удалось загрузить данные"))
      .finally(() => setLoading(false));
  }, [open, fileId]);

  const meta = useMemo(() => {
    if (!file) return [];
    const shotAt = file.shot_at ? new Date(file.shot_at).toLocaleString() : "—";
    return [
      { label: "Тайтл", value: file.title ?? "—" },
      { label: "Описание", value: file.description ?? "—" },
      { label: "Файл", value: file.filename },
      { label: "Размер", value: `${Math.round(file.size_bytes / 1024)} KB` },
      { label: "Формат", value: file.mime },
      { label: "Дата съемки", value: shotAt },
      { label: "Ориентация", value: file.orientation },
    ];
  }, [file]);

  const terms = useMemo(() => extractTerms(query), [query]);

  const handleAddKeyword = () => {
    const trimmed = keywordInput.trim();
    if (!trimmed || keywords.includes(trimmed)) return;
    setKeywords((prev) => [...prev, trimmed]);
    setKeywordInput("");
  };

  const handleSave = async () => {
    if (!file) return;
    setSaving(true);
    setError("");
    const removed = file.keywords.filter((kw) => !keywords.includes(kw));
    const added = keywords.filter((kw) => !file.keywords.includes(kw));
    try {
      const updated = await updateKeywords(file.id, { add: added, remove: removed });
      setFile(updated);
      setKeywords(updated.keywords);
    } catch {
      setError("Не удалось сохранить keywords");
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = async () => {
    if (!file) return;
    try {
      const { token } = await getDownloadToken(file.id);
      window.location.href = `/api/download/${token}`;
    } catch {
      setError("Не удалось получить ссылку для скачивания");
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Детали фото
        </Typography>
        <IconButton onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
            <CircularProgress />
          </Box>
        ) : file ? (
          <Box sx={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 3 }}>
            <Box
              component="img"
              src={withAccessToken(file.medium_url)}
              alt={file.filename}
              sx={{ width: "100%", borderRadius: 2 }}
            />
            <Stack spacing={2}>
              <Stack direction="row" spacing={1}>
                <Button
                  variant="contained"
                  startIcon={<CloudDownloadIcon />}
                  onClick={handleDownload}
                >
                  Скачать оригинал
                </Button>
              </Stack>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Keywords
                </Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
                  {keywords.map((kw) => (
                    <Chip
                      key={kw}
                      label={highlightText(kw, terms)}
                      onDelete={() => setKeywords((prev) => prev.filter((item) => item !== kw))}
                      sx={{ mb: 1 }}
                    />
                  ))}
                </Stack>
                <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                  <TextField
                    size="small"
                    label="Добавить keyword"
                    value={keywordInput}
                    onChange={(event) => setKeywordInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        handleAddKeyword();
                      }
                    }}
                  />
                  <Button variant="outlined" onClick={handleAddKeyword}>
                    Добавить
                  </Button>
                </Stack>
                <Button
                  variant="text"
                  sx={{ mt: 1 }}
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? "Сохранение..." : "Сохранить"}
                </Button>
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Метаданные
                </Typography>
                <Stack spacing={0.5}>
                  {meta.map((item) => (
                    <Typography variant="body2" key={item.label}>
                      {item.label}: {highlightText(String(item.value), terms)}
                    </Typography>
                  ))}
                </Stack>
              </Box>
              {error && (
                <Typography variant="body2" color="error">
                  {error}
                </Typography>
              )}
            </Stack>
          </Box>
        ) : (
          <Typography variant="body2">Файл не найден</Typography>
        )}
      </DialogContent>
    </Dialog>
  );
}
