import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Button,
  Container,
  Paper,
  TextField,
  Typography,
} from "@mui/material";
import { login } from "../api/auth";
import { useAuth } from "../auth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { setTokens } = useAuth();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      const data = await login({ email, password });
      setTokens({ accessToken: data.access_token, refreshToken: data.refresh_token });
      navigate("/", { replace: true });
    } catch {
      setError("Неверные учетные данные");
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        background: "linear-gradient(135deg, #f8f3e5 0%, #f1f5f9 60%)",
      }}
    >
      <Container maxWidth="sm">
        <Paper elevation={6} sx={{ p: 4, borderRadius: 3 }}>
          <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>
            Поиск фото
          </Typography>
          <Typography variant="body1" sx={{ mb: 3, color: "text.secondary" }}>
            Войдите, чтобы искать и скачивать оригиналы.
          </Typography>
          <Box component="form" onSubmit={handleSubmit}>
            <TextField
              label="Email"
              type="email"
              fullWidth
              margin="normal"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <TextField
              label="Пароль"
              type="password"
              fullWidth
              margin="normal"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            {error && (
              <Typography variant="body2" color="error" sx={{ mt: 1 }}>
                {error}
              </Typography>
            )}
            <Button
              variant="contained"
              size="large"
              fullWidth
              sx={{ mt: 2 }}
              type="submit"
            >
              Войти
            </Button>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}
