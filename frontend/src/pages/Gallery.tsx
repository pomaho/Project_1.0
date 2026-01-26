import {
  AppBar,
  Box,
  Chip,
  Container,
  InputAdornment,
  TextField,
  Toolbar,
  Typography,
  CircularProgress,
  Autocomplete,
  Button,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import AdminPanelSettingsIcon from "@mui/icons-material/AdminPanelSettings";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { searchPhotos, suggestKeywords } from "../api/search";
import { getDownloadToken } from "../api/files";
import useDebounce from "../hooks/useDebounce";
import PhotoGrid from "../components/PhotoGrid";
import PhotoDetails from "../components/PhotoDetails";
import { useAuth } from "../auth";

export default function GalleryPage() {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const debounced = useDebounce(query, 300);
  const { logout } = useAuth();

  const searchQuery = useInfiniteQuery({
    queryKey: ["search", debounced],
    queryFn: ({ pageParam = 0 }) => searchPhotos(debounced, pageParam as number),
    getNextPageParam: (lastPage) =>
      lastPage.next_cursor ? Number(lastPage.next_cursor) : undefined,
    initialPageParam: 0,
  });

  const suggestionsQuery = useQuery({
    queryKey: ["suggest", debounced],
    queryFn: () => suggestKeywords(debounced),
    enabled: debounced.length > 0,
  });

  const items = useMemo(
    () => searchQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [searchQuery.data]
  );

  return (
    <Box sx={{ minHeight: "100vh", backgroundColor: "#f7f1ea" }}>
      <AppBar
        position="sticky"
        color="transparent"
        elevation={0}
        sx={{ backdropFilter: "blur(8px)" }}
      >
        <Toolbar>
          <Typography variant="h6" sx={{ fontWeight: 700, flexGrow: 1 }}>
            Поиск по ключевым словам
          </Typography>
          <Chip label="Editor" size="small" color="secondary" />
          <Button
            variant="text"
            color="inherit"
            startIcon={<AdminPanelSettingsIcon />}
            href="/admin"
            sx={{ ml: 2 }}
          >
            Admin
          </Button>
          <Button variant="text" color="inherit" onClick={logout}>
            Выйти
          </Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: 4, height: "calc(100vh - 64px)" }}>
        <Autocomplete
          freeSolo
          options={(suggestionsQuery.data ?? []).map((item) => item.value)}
          inputValue={query}
          onInputChange={(_, value) => setQuery(value)}
          renderInput={(params) => (
            <TextField
              {...params}
              fullWidth
              placeholder='Поиск: "red dress" wedding OR studio -outdoor'
              InputProps={{
                ...params.InputProps,
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
                endAdornment: (
                  <>
                    {searchQuery.isFetching ? (
                      <CircularProgress color="inherit" size={18} />
                    ) : null}
                    {params.InputProps.endAdornment}
                  </>
                ),
              }}
              sx={{ mb: 3, backgroundColor: "white", borderRadius: 2 }}
            />
          )}
        />
        <Box sx={{ height: "calc(100% - 96px)" }}>
          <PhotoGrid
            items={items}
            onEndReached={() => {
              if (searchQuery.hasNextPage && !searchQuery.isFetchingNextPage) {
                searchQuery.fetchNextPage();
              }
            }}
            onSelect={(item) => setSelectedId(item.id)}
            onDownload={async (item) => {
              try {
                const { token } = await getDownloadToken(item.id);
                window.location.href = `/api/download/${token}`;
              } catch {
                setSelectedId(item.id);
              }
            }}
          />
        </Box>
      </Container>
      <PhotoDetails
        fileId={selectedId}
        open={Boolean(selectedId)}
        onClose={() => setSelectedId(null)}
      />
    </Box>
  );
}
