import type { FormEvent, ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  Link,
  Navigate,
  NavLink,
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
};

type AppShellProps = {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
};

type CreatedState = {
  jobName: string;
  fileCount: number;
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadJobs() {
      setLoading(true);
      setError(null);

      try {
        const response = await authFetch(`/api/v1/jobs?sort_by=${sortField}&sort_order=${sortOrder}`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Failed to load jobs (${response.status})`);
        }

        const data: Job[] = await response.json();
        setJobs(data);
      } catch (fetchError) {
        if (fetchError instanceof DOMException && fetchError.name === "AbortError") {
          return;
        }

        setError(fetchError instanceof Error ? fetchError.message : "Failed to load jobs");
      } finally {
        setLoading(false);
      }
    }

    void loadJobs();

    return () => controller.abort();
  }, [authFetch, sortField, sortOrder]);

  function toggleSort(field: SortField) {
    if (field === sortField) {
      setSortOrder((currentOrder) => (currentOrder === "asc" ? "desc" : "asc"));
      return;
    }

    setSortField(field);
    setSortOrder(field === "created_at" ? "desc" : "asc");
  }

  function getSortIndicator(field: SortField) {
    if (field !== sortField) {
      return "";
    }

    return sortOrder === "asc" ? " ↑" : " ↓";
  }

  return (
    <AppShell
      title="Recent jobs"
      actions={
        <>
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
                  {error}
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
    </AppShell>
  );
}

function CreateJobPage() {
  const navigate = useNavigate();
  const [jobName, setJobName] = useState("");
  const [files, setFiles] = useState<File[]>([]);

  return (
    <AppShell title="Create new job">
      <form
        className="job-form"
        onSubmit={(event) => {
          event.preventDefault();

          if (!jobName.trim() || files.length === 0) {
            return;
          }

          const createdId = crypto.randomUUID();
          const state: CreatedState = { jobName: jobName.trim(), fileCount: files.length };

          navigate(`/jobs/${createdId}/created`, { state });
        }}
      >
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
          <span>Images or documents</span>
          <input
            className="file-input"
            type="file"
            multiple
            accept="image/*,.pdf"
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            required
          />
        </label>

        <div className="files-preview" aria-live="polite">
          {files.length === 0 ? "No files selected." : `${files.length} file(s) selected`}
        </div>

        <button type="submit" className="btn btn--primary btn--wide" disabled={!jobName.trim() || files.length === 0}>
          Create
        </button>
      </form>
    </AppShell>
  );
}

function JobCreatedPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as CreatedState | null) ?? null;

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
          {state ? `Job name: ${state.jobName}. Files in queue: ${state.fileCount}.` : "You can track status from the recent jobs table."}
        </p>
      </section>
    </AppShell>
  );
}

function ResultsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [jobId, setJobId] = useState(searchParams.get("jobId") ?? "");
  const [loaded, setLoaded] = useState(Boolean(searchParams.get("jobId")));

  return (
    <AppShell title="Get results">
      <form
        className="job-form"
        onSubmit={(event) => {
          event.preventDefault();

          if (!jobId.trim()) {
            return;
          }

          setLoaded(true);
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
          Get results
        </button>

        <section className="results-panel" aria-live="polite">
          {!loaded ? (
            <p className="notice-muted">Resulting images will appear here after lookup.</p>
          ) : (
            <div className="result-grid">
              <article className="result-card">{jobId}-face-01.png</article>
              <article className="result-card">{jobId}-car-plate-02.png</article>
              <article className="result-card">{jobId}-document-03.pdf</article>
            </div>
          )}
        </section>

        <button type="button" className="btn" onClick={() => navigate("/")}>
          Go to main screen
        </button>
      </form>
    </AppShell>
  );
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
