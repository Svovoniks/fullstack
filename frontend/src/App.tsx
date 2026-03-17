import type { FormEvent, ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  Link,
  Navigate,
  NavLink,
  useParams,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";

import { useAuth } from "./auth";

type JobStatus = "queued" | "processing" | "completed" | "failed";
type SortField = "created_at" | "id" | "name" | "status" | "filename";
type SortOrder = "asc" | "desc";

type Job = {
  id: string;
  name: string;
  filename: string;
  status: JobStatus;
  created_at: string;
  source_object_key: string | null;
  result_object_key: string | null;
  content_type: string | null;
  result_content_type: string | null;
  error_message: string | null;
};

type JobsPageResponse = {
  items: Job[];
  next_cursor: string | null;
};

type AppShellProps = {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
};

type CreatedState = {
  jobs: Job[];
};

type AuthLocationState = {
  from?: {
    pathname: string;
    search: string;
  };
};

const DEFAULT_SORT_FIELD: SortField = "created_at";
const DEFAULT_SORT_ORDER: SortOrder = "desc";
const SORTABLE_COLUMNS: { field: SortField; label: string }[] = [
  { field: "created_at", label: "Created" },
  { field: "id", label: "ID" },
  { field: "name", label: "Name" },
  { field: "filename", label: "Filename" },
  { field: "status", label: "Status" },
];

async function readErrorMessage(response: Response) {
  const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
  return payload?.detail ?? `Request failed (${response.status})`;
}

function formatJobStatus(status: JobStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

async function loadProtectedAsset(authFetch: ReturnType<typeof useAuth>["authFetch"], path: string) {
  const response = await authFetch(path);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

function AuthStatusBadge() {
  const { status, session } = useAuth();

  if (status === "loading") {
    return <span className="auth-pill auth-pill--loading">Checking session</span>;
  }

  if (status === "authenticated" && session) {
    return <span className="auth-pill auth-pill--ready">{session.username}</span>;
  }

  return <span className="auth-pill">Signed out</span>;
}

function AppShell({ title, children, actions }: AppShellProps) {
  const { status, logout } = useAuth();

  return (
    <main className="app-root">
      <section className="screen-frame">
        <div className="screen-inner">
          <header className="screen-header">
            <div>
              <p className="screen-caption">personal data redaction</p>
              <h1>{title}</h1>
            </div>
            <div className="header-controls">
              <nav className="top-nav" aria-label="Primary">
                <NavLink to="/" end className={({ isActive }) => (isActive ? "top-nav__link top-nav__link--active" : "top-nav__link")}>
                  Recent jobs
                </NavLink>
                <NavLink to="/jobs/new" className={({ isActive }) => (isActive ? "top-nav__link top-nav__link--active" : "top-nav__link")}>
                  New job
                </NavLink>
                <NavLink to="/results" className={({ isActive }) => (isActive ? "top-nav__link top-nav__link--active" : "top-nav__link")}>
                  Get results
                </NavLink>
              </nav>
              <div className="auth-bar">
                <AuthStatusBadge />
                <button type="button" className="btn btn--ghost" onClick={logout} disabled={status !== "authenticated"}>
                  Logout
                </button>
              </div>
            </div>
          </header>
          {actions ? <div className="screen-actions">{actions}</div> : null}
          {children}
        </div>
      </section>
    </main>
  );
}

function AuthLoadingScreen() {
  return (
    <main className="app-root auth-screen">
      <section className="auth-card">
        <p className="screen-caption">authorization</p>
        <h1>Restoring session</h1>
        <p className="notice-muted">Checking local tokens and auth state.</p>
      </section>
    </main>
  );
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <AuthLoadingScreen />;
  }

  if (status === "unauthenticated") {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: { pathname: location.pathname, search: location.search } }}
      />
    );
  }

  return <>{children}</>;
}

function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { status, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const redirectTarget = (location.state as AuthLocationState | null)?.from;

  useEffect(() => {
    if (status === "authenticated") {
      navigate(redirectTarget ? `${redirectTarget.pathname}${redirectTarget.search}` : "/", { replace: true });
    }
  }, [navigate, redirectTarget, status]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login({ username, password });
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="app-root auth-screen">
      <section className="auth-card">
        <p className="screen-caption">client authorization</p>
        <h1>Sign in</h1>
        <p className="notice-muted">
          Use your backend account to restore protected access to jobs and results.
        </p>
        <form className="job-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Username</span>
            <input
              className="input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Enter your username"
              autoComplete="username"
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
              required
            />
          </label>
          {error ? <div className="inline-message inline-message--error">{error}</div> : null}
          <button type="submit" className="btn btn--primary btn--wide" disabled={submitting}>
            {submitting ? "Signing in..." : "Sign in"}
          </button>
          <p className="auth-switch">
            Need an account? <Link className="auth-link" to="/signup">Create one</Link>
          </p>
        </form>
      </section>
    </main>
  );
}

function SignupPage() {
  const navigate = useNavigate();
  const { status, signup } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") {
      navigate("/", { replace: true });
    }
  }, [navigate, status]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await signup({ username, password });
    } catch (signupError) {
      setError(signupError instanceof Error ? signupError.message : "Unable to sign up");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="app-root auth-screen">
      <section className="auth-card">
        <p className="screen-caption">client authorization</p>
        <h1>Sign up</h1>
        <p className="notice-muted">
          Create a backend account. Your password is stored as a secure hash in PostgreSQL.
        </p>
        <form className="job-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Username</span>
            <input
              className="input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Choose a username"
              autoComplete="username"
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              autoComplete="new-password"
              required
            />
          </label>
          <label className="field">
            <span>Confirm password</span>
            <input
              className="input"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Repeat your password"
              autoComplete="new-password"
              required
            />
          </label>
          {error ? <div className="inline-message inline-message--error">{error}</div> : null}
          <button type="submit" className="btn btn--primary btn--wide" disabled={submitting}>
            {submitting ? "Creating account..." : "Create account"}
          </button>
          <p className="auth-switch">
            Already have an account? <Link className="auth-link" to="/login">Sign in</Link>
          </p>
        </form>
      </section>
    </main>
  );
}

function JobsPage() {
  const navigate = useNavigate();
  const { authFetch } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [sortField, setSortField] = useState<SortField>(DEFAULT_SORT_FIELD);
  const [sortOrder, setSortOrder] = useState<SortOrder>(DEFAULT_SORT_ORDER);
  const [currentCursor, setCurrentCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadJobs() {
      setLoading(true);
      setError(null);

      try {
        const query = new URLSearchParams({
          sort_by: sortField,
          sort_order: sortOrder,
        });
        if (currentCursor) {
          query.set("cursor", currentCursor);
        }

        const response = await authFetch(`/api/v1/jobs?${query.toString()}`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(await readErrorMessage(response));
        }

        const data: JobsPageResponse = await response.json();
        setJobs(data.items);
        setNextCursor(data.next_cursor);
      } catch (fetchError) {
        if (fetchError instanceof DOMException && fetchError.name === "AbortError") {
          return;
        }

        setError(fetchError instanceof Error ? fetchError.message : "Failed to load jobs");
        setNextCursor(null);
      } finally {
        setLoading(false);
      }
    }

    void loadJobs();

    return () => controller.abort();
  }, [authFetch, currentCursor, reloadKey, sortField, sortOrder]);

  function toggleSort(field: SortField) {
    if (field === sortField) {
      setSortOrder((currentOrder) => (currentOrder === "asc" ? "desc" : "asc"));
      setCurrentCursor(null);
      setCursorHistory([]);
      return;
    }

    setSortField(field);
    setSortOrder(field === "created_at" ? "desc" : "asc");
    setCurrentCursor(null);
    setCursorHistory([]);
  }

  function getSortIndicator(field: SortField) {
    if (field !== sortField) {
      return "";
    }

    return sortOrder === "asc" ? " ↑" : " ↓";
  }

  function handleRefresh() {
    setCurrentCursor(null);
    setCursorHistory([]);
    setReloadKey((value) => value + 1);
  }

  function handleNextPage() {
    if (!nextCursor || loading) {
      return;
    }

    setCursorHistory((history) => [...history, currentCursor ?? ""]);
    setCurrentCursor(nextCursor);
  }

  function handlePreviousPage() {
    if (cursorHistory.length === 0 || loading) {
      return;
    }

    const previousCursor = cursorHistory[cursorHistory.length - 1];
    setCursorHistory((history) => history.slice(0, -1));
    setCurrentCursor(previousCursor || null);
  }

  const currentPage = cursorHistory.length + 1;

  return (
    <AppShell
      title="Recent jobs"
      actions={
        <>
          <button type="button" className="btn btn--ghost" onClick={handleRefresh} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <button type="button" className="btn btn--primary" onClick={() => navigate("/results")}>
            Get results
          </button>
          <button type="button" className="btn" onClick={() => navigate("/jobs/new")}>
            New job
          </button>
        </>
      }
    >
      <div className="table-wrap">
        <table className="jobs-table">
          <thead>
            <tr>
              {SORTABLE_COLUMNS.map((column) => (
                <th key={column.field}>
                  <button type="button" className="sort-button" onClick={() => toggleSort(column.field)}>
                    {column.label}
                    {getSortIndicator(column.field)}
                  </button>
                </th>
              ))}
              <th>Link</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="table-state">
                  Loading recent jobs...
                </td>
              </tr>
            ) : null}
            {!loading && error ? (
              <tr>
                <td colSpan={6} className="table-state table-state--error">
                  <div className="table-feedback">
                    <span>{error}</span>
                    <button type="button" className="btn btn--ghost" onClick={() => setReloadKey((value) => value + 1)}>
                      Try again
                    </button>
                  </div>
                </td>
              </tr>
            ) : null}
            {!loading && !error && jobs.length === 0 ? (
              <tr>
                <td colSpan={6} className="table-state">
                  No jobs found.
                </td>
              </tr>
            ) : null}
            {!loading && !error && jobs.map((job) => (
              <tr key={job.id}>
                <td>{new Date(job.created_at).toLocaleString()}</td>
                <td>{job.id}</td>
                <td>{job.name}</td>
                <td>{job.filename}</td>
                <td>
                  <span className={`status status--${job.status}`}>{job.status}</span>
                </td>
                <td>
                  <Link className="table-link" to={`/results?jobId=${job.id}`}>
                    Open
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination-bar" aria-label="Recent jobs pagination">
        <span className="pagination-summary">Page {currentPage} · Up to 20 entries</span>
        <div className="pagination-actions">
          <button type="button" className="btn btn--ghost" onClick={handlePreviousPage} disabled={loading || cursorHistory.length === 0}>
            Previous
          </button>
          <button type="button" className="btn btn--ghost" onClick={handleNextPage} disabled={loading || !nextCursor}>
            Next
          </button>
        </div>
      </div>
    </AppShell>
  );
}

function CreateJobPage() {
  const navigate = useNavigate();
  const { authFetch } = useAuth();
  const [jobName, setJobName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedName = jobName.trim();
    if (!trimmedName || files.length === 0) {
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const createdJobs = await Promise.all(
        files.map(async (file, index) => {
          const formData = new FormData();
          formData.append("name", files.length > 1 ? `${trimmedName} ${index + 1}` : trimmedName);
          formData.append("file", file);

          const response = await authFetch("/api/v1/jobs", {
            method: "POST",
            body: formData,
          });

          if (!response.ok) {
            throw new Error(await readErrorMessage(response));
          }

          return (await response.json()) as Job;
        }),
      );

      const state: CreatedState = { jobs: createdJobs };
      navigate(`/jobs/${createdJobs[0].id}/created`, { state });
    } catch (creationError) {
      setError(creationError instanceof Error ? creationError.message : "Failed to create job");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppShell title="Create new job">
      <form className="job-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Name</span>
          <input
            className="input"
            value={jobName}
            onChange={(event) => setJobName(event.target.value)}
            placeholder="e.g. parking-batch-02"
            required
          />
        </label>

        <label className="field">
          <span>Images</span>
          <input
            className="file-input"
            type="file"
            multiple
            accept="image/*"
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            required
          />
        </label>

        <div className="files-preview" aria-live="polite">
          {files.length === 0 ? "No files selected." : `${files.length} file(s) selected`}
        </div>

        {error ? <div className="inline-message inline-message--error">{error}</div> : null}

        <button type="submit" className="btn btn--primary btn--wide" disabled={submitting || !jobName.trim() || files.length === 0}>
          {submitting ? "Creating..." : "Create"}
        </button>
      </form>
    </AppShell>
  );
}

function JobCreatedPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as CreatedState | null) ?? null;
  const createdJobs = state?.jobs ?? [];

  return (
    <AppShell
      title="Job created"
      actions={
        <button type="button" className="btn btn--primary" onClick={() => navigate("/")}>
          Go to main screen
        </button>
      }
    >
      <section className="notice-card">
        <p>
          New job created id <code>{location.pathname.split("/")[2]}</code>
        </p>
        <p className="notice-muted">
          {createdJobs.length > 0
            ? `${createdJobs.length} job(s) added to the queue.`
            : "You can track status from the recent jobs table."}
        </p>
        {createdJobs.length > 0 ? (
          <div className="created-jobs-list">
            {createdJobs.map((job) => (
              <article key={job.id} className="result-card">
                <strong>{job.name}</strong>
                <span>{job.filename}</span>
                <span className={`status status--${job.status}`}>{job.status}</span>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}

function ResultsPage() {
  const navigate = useNavigate();
  const { authFetch } = useAuth();
  const [searchParams] = useSearchParams();
  const initialJobId = searchParams.get("jobId") ?? "";
  const [jobId, setJobId] = useState(initialJobId);
  const [lookupId, setLookupId] = useState(initialJobId);
  const [loading, setLoading] = useState(Boolean(initialJobId));
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [sourcePreviewUrl, setSourcePreviewUrl] = useState<string | null>(null);
  const [resultPreviewUrl, setResultPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (sourcePreviewUrl) {
        URL.revokeObjectURL(sourcePreviewUrl);
      }
      if (resultPreviewUrl) {
        URL.revokeObjectURL(resultPreviewUrl);
      }
    };
  }, [resultPreviewUrl, sourcePreviewUrl]);

  useEffect(() => {
    if (!lookupId) {
      setLoading(false);
      setError(null);
      setJob(null);
      return;
    }

    const controller = new AbortController();

    async function loadJob() {
      setLoading(true);
      setError(null);

      try {
        const response = await authFetch(`/api/v1/jobs/${lookupId}`, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(await readErrorMessage(response));
        }

        const data = (await response.json()) as Job;
        setJob(data);
      } catch (fetchError) {
        if (fetchError instanceof DOMException && fetchError.name === "AbortError") {
          return;
        }

        setJob(null);
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load job");
      } finally {
        setLoading(false);
      }
    }

    void loadJob();

    return () => controller.abort();
  }, [authFetch, lookupId]);

  useEffect(() => {
    let cancelled = false;

    async function loadAssets() {
      if (!job) {
        setSourcePreviewUrl((current) => {
          if (current) {
            URL.revokeObjectURL(current);
          }
          return null;
        });
        setResultPreviewUrl((current) => {
          if (current) {
            URL.revokeObjectURL(current);
          }
          return null;
        });
        return;
      }

      try {
        const sourceUrl = job.source_object_key
          ? await loadProtectedAsset(authFetch, `/api/v1/jobs/${job.id}/source`)
          : null;
        const resultUrl = job.result_object_key
          ? await loadProtectedAsset(authFetch, `/api/v1/jobs/${job.id}/result`)
          : null;

        if (cancelled) {
          if (sourceUrl) {
            URL.revokeObjectURL(sourceUrl);
          }
          if (resultUrl) {
            URL.revokeObjectURL(resultUrl);
          }
          return;
        }

        setSourcePreviewUrl((current) => {
          if (current) {
            URL.revokeObjectURL(current);
          }
          return sourceUrl;
        });
        setResultPreviewUrl((current) => {
          if (current) {
            URL.revokeObjectURL(current);
          }
          return resultUrl;
        });
      } catch (assetError) {
        if (!cancelled) {
          setError(assetError instanceof Error ? assetError.message : "Failed to load stored images");
        }
      }
    }

    void loadAssets();

    return () => {
      cancelled = true;
    };
  }, [authFetch, job]);

  return (
    <AppShell title="Get results">
      <form
        className="job-form"
        onSubmit={(event) => {
          event.preventDefault();

          if (!jobId.trim()) {
            return;
          }

          setLookupId(jobId.trim());
        }}
      >
        <label className="field">
          <span>Job ID</span>
          <input
            className="input"
            value={jobId}
            onChange={(event) => setJobId(event.target.value)}
            placeholder="2f37f63b-7341-46e6-80d7-2d23d373efca"
            required
          />
        </label>

        <button type="submit" className="btn btn--primary btn--wide">
          {loading ? "Loading..." : "Get results"}
        </button>

        <section className="results-panel" aria-live="polite">
          {!lookupId ? (
            <p className="notice-muted">Resulting images will appear here after lookup.</p>
          ) : loading ? (
            <p className="notice-muted">Loading job details from the backend...</p>
          ) : error ? (
            <div className="results-feedback">
              <p className="inline-message inline-message--error">{error}</p>
              <button type="button" className="btn btn--ghost" onClick={() => setLookupId(jobId.trim())} disabled={!jobId.trim()}>
                Try again
              </button>
            </div>
          ) : job ? (
            <>
              <div className="result-grid">
                <article className="result-card">
                  <strong>ID</strong>
                  <span>{job.id}</span>
                </article>
                <article className="result-card">
                  <strong>Name</strong>
                  <span>{job.name}</span>
                </article>
                <article className="result-card">
                  <strong>Filename</strong>
                  <span>{job.filename}</span>
                </article>
                <article className="result-card">
                  <strong>Status</strong>
                  <span className={`status status--${job.status}`}>{formatJobStatus(job.status)}</span>
                </article>
                <article className="result-card">
                  <strong>Created</strong>
                  <span>{new Date(job.created_at).toLocaleString()}</span>
                </article>
              </div>
              {job.error_message ? <p className="inline-message inline-message--error">{job.error_message}</p> : null}
              <div className="result-grid result-grid--media">
                <article className="result-card">
                  <strong>Source image</strong>
                  {sourcePreviewUrl ? <img className="result-preview" src={sourcePreviewUrl} alt={`Source for ${job.filename}`} /> : <span>Not available</span>}
                  {job.source_object_key ? <a className="table-link" href={sourcePreviewUrl ?? "#"} download={job.filename}>Download source</a> : null}
                </article>
                <article className="result-card">
                  <strong>Processed image</strong>
                  {resultPreviewUrl ? <img className="result-preview" src={resultPreviewUrl} alt={`Processed result for ${job.filename}`} /> : <span>Processing has not produced a result yet.</span>}
                  {job.result_object_key ? <a className="table-link" href={resultPreviewUrl ?? "#"} download={`processed-${job.filename}`}>Download result</a> : null}
                </article>
              </div>
            </>
          ) : (
            <p className="notice-muted">No data found for this job.</p>
          )}
        </section>

        <button type="button" className="btn" onClick={() => navigate("/")}>
          Go to main screen
        </button>
      </form>
    </AppShell>
  );
}

function JobRedirectPage() {
  const { jobId } = useParams();

  if (!jobId) {
    return <Navigate to="/results" replace />;
  }

  return <Navigate to={`/results?jobId=${jobId}`} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <JobsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/jobs/new"
        element={
          <ProtectedRoute>
            <CreateJobPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/jobs/:jobId/created"
        element={
          <ProtectedRoute>
            <JobCreatedPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/jobs/:jobId"
        element={
          <ProtectedRoute>
            <JobRedirectPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/results"
        element={
          <ProtectedRoute>
            <ResultsPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
