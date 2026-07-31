import { Component, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined" && window.location.port === "5173"
    ? "http://localhost:8000/api"
    : "/api")
).trim();
const apiKey = (import.meta.env.VITE_API_KEY || "").trim();

function getSessionId() {
  const key = "second_brain_session_id";
  try {
    const existing = window.localStorage.getItem(key);
    if (existing) return existing;
  } catch {
    return `sb-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  const generated =
    window.crypto?.randomUUID?.() ||
    `sb-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  try {
    window.localStorage.setItem(key, generated);
  } catch {
    // Storage can be unavailable in some mobile/private browsers.
  }
  return generated;
}

const sessionId = getSessionId();

const api = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "X-Session-Id": sessionId,
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  },
});

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error) {
    console.error("UI recovered from an error:", error);
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="app-shell app-root error-boundary-screen">
        <div className="workspace-card error-boundary-card">
          <h1>Workspace recovered</h1>
          <p>A screen section failed to render. Continue without reloading the whole app.</p>
          <button className="primary-button" onClick={() => this.setState({ hasError: false })}>
            Continue
          </button>
        </div>
      </div>
    );
  }
}

const sidebarSections = [
  { id: "dashboard", label: "Dashboard" },
  { id: "notes", label: "Notes" },
  { id: "chat", label: "Ask AI" },
  { id: "graph", label: "Knowledge Graph" },
  { id: "upload", label: "Upload" },
  { id: "study", label: "Study" },
];

const railSections = [
  { id: "chat", label: "Chat", short: "C" },
  { id: "notes", label: "Notes", short: "N" },
  { id: "upload", label: "Upload", short: "U" },
  { id: "dashboard", label: "Analytics", short: "A" },
  { id: "study", label: "Study", short: "S" },
  { id: "graph", label: "Graph", short: "G" },
];

const quickActions = [
  { label: "Explain", buildPrompt: (text) => (text ? `Explain this clearly with simple steps:\n${text}` : "Explain the most important concept from my uploaded knowledge.") },
  { label: "Summary", buildPrompt: (text) => (text ? `Summarize this into clear bullet points:\n${text}` : "Summarize the most relevant knowledge I have uploaded.") },
  { label: "Revise", buildPrompt: (text) => (text ? `Give me revision notes for this topic:\n${text}` : "Give me revision notes from my uploaded material.") },
  { label: "Next", buildPrompt: () => "next" },
];

const starterPrompts = [
  "Explain this topic with a mini diagram.",
  "Summarize this chapter and show the flow.",
  "Compare two ideas with a simple visual map.",
  "Teach this step by step with an example.",
];

const capabilityCards = [
  {
    label: "Upload",
    title: "Add your material",
    text: "PDFs, images, YouTube videos, notes, and transcripts become searchable knowledge.",
    action: "Add source",
    target: "upload",
  },
  {
    label: "Ask",
    title: "Get grounded answers",
    text: "Ask questions, request summaries, compare ideas, and get answers from your uploaded sources.",
    action: "Ask AI",
    target: "chat",
  },
  {
    label: "Study",
    title: "Revise smarter",
    text: "Create flashcards, find weak topics, build concept maps, and follow a study path.",
    action: "Study plan",
    target: "study",
  },
];

const benefitCards = [
  { title: "Video to notes", text: "Paste a YouTube link or transcript and turn it into key points, questions, and revision notes." },
  { title: "PDF tutor", text: "Upload a chapter or report, then ask the AI to explain, summarize, or teach it step by step." },
  { title: "Memory workspace", text: "Save notes and keep your sources connected so the assistant remembers your learning context." },
  { title: "Exam practice", text: "Generate flashcards and weak-topic practice from the exact material you added." },
];

const workflowCards = [
  {
    title: "Summarize my source",
    text: "Best after uploading a PDF, image, or YouTube transcript.",
    prompt: "Summarize my active source with key ideas, examples, and revision points.",
  },
  {
    title: "Teach me step by step",
    text: "Turns dense content into a simple learning flow.",
    prompt: "Teach the active source step by step like I am learning it for the first time.",
  },
  {
    title: "Make a practice plan",
    text: "Creates questions, flashcards, and what to revise next.",
    prompt: "Create a study plan from my active source with practice questions and weak areas.",
  },
];

const statusChecks = [
  { key: "llm_ready", label: "AI answer engine", ready: "Groq connected", blocked: "Needs Groq API key" },
  { key: "ingestion_ready", label: "PDF + YouTube ingestion", ready: "Core ingestion ready", blocked: "Missing ingestion dependency" },
  { key: "embedding_model_ready", label: "Semantic retrieval", ready: "Transformer retrieval ready", blocked: "Fast hash retrieval active" },
];

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
const UPLOAD_TIMEOUT_MS = 300000;
const PDF_TYPES = new Set(["application/pdf"]);
const IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/jpg", "image/webp"]);

const navMeta = {
  dashboard: { icon: "D", count: null },
  notes: { icon: "N", count: "notes" },
  chat: { icon: "A", count: null },
  graph: { icon: "G", count: null },
  upload: { icon: "U", count: null },
  study: { icon: "S", count: null },
};

function TopicPill({ topic }) {
  return <span className="topic-pill">{topic || "General"}</span>;
}

function EmptyHint({ title, text, action, onClick }) {
  return (
    <div className="empty-hint">
      <strong>{title}</strong>
      <p>{text}</p>
      {action && <button className="ghost-button" onClick={onClick}>{action}</button>}
    </div>
  );
}

export default function SecondBrainApp() {
  return (
    <ErrorBoundary>
      <SecondBrainAppContent />
    </ErrorBoundary>
  );
}

function unwrapPayload(payload) {
  return payload?.data ?? payload;
}

function normalizeAssistantText(text) {
  const cleaned = String(text || "").trim();
  return cleaned || "I am here, but I could not form a complete answer yet. Try asking in a more specific way.";
}

function formatMessageTime(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function parseDiagramLines(lines) {
  return lines
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/^[-*]\s*/, ""));
}

function DiagramBlock({ lines }) {
  const cleanedLines = parseDiagramLines(lines);

  return (
    <div className="diagram-block">
      {cleanedLines.map((line, index) => {
        const flowParts = line.split("->").map((part) => part.trim()).filter(Boolean);

        if (flowParts.length > 1) {
          return (
            <div className="diagram-flow" key={`${line}-${index}`}>
              {flowParts.map((part, partIndex) => (
                <div className="diagram-flow-part" key={`${part}-${partIndex}`}>
                  <span className="diagram-node">{part}</span>
                  {partIndex < flowParts.length - 1 && <span className="diagram-arrow">-&gt;</span>}
                </div>
              ))}
            </div>
          );
        }

        return (
          <div className="diagram-line" key={`${line}-${index}`}>
            <span className="diagram-node">{line}</span>
          </div>
        );
      })}
    </div>
  );
}

function MessageBody({ text }) {
  const normalizedText = normalizeAssistantText(text);
  const blocks = normalizedText.split(/\n\s*\n/).filter(Boolean);
  const sectionLabels = new Set([
    "direct answer",
    "main explanation",
    "key points",
    "example",
    "short summary",
    "formula / concept",
    "step-by-step solution",
    "mini diagram",
    "final result",
    "short intuition",
    "question focus",
  ]);

  return (
    <div className="message-body">
      {blocks.map((block, index) => {
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        const listLike = lines.length > 1 && lines.every((line) => /^([-*]|\d+\.)\s/.test(line));

        if (listLike) {
          return (
            <ul className="message-list" key={`${block.slice(0, 20)}-${index}`}>
              {lines.map((line) => (
                <li key={line}>{line.replace(/^([-*]|\d+\.)\s/, "")}</li>
              ))}
            </ul>
          );
        }

        if (lines.length === 1 && sectionLabels.has(lines[0].replace(/:$/, "").toLowerCase())) {
          return <h4 className="message-section-title" key={`${block.slice(0, 20)}-${index}`}>{lines[0]}</h4>;
        }

        if (lines.length > 1 && lines[0].replace(/:$/, "").toLowerCase() === "mini diagram") {
          return <DiagramBlock key={`${block.slice(0, 20)}-${index}`} lines={lines.slice(1)} />;
        }

        return <p key={`${block.slice(0, 20)}-${index}`}>{block}</p>;
      })}
    </div>
  );
}

function SecondBrainAppContent() {
  const [authForm, setAuthForm] = useState(() => {
    try {
      return {
        name: window.localStorage.getItem("second_brain_user_name") || "",
        email: window.localStorage.getItem("second_brain_user_email") || "",
      };
    } catch {
      return { name: "", email: "" };
    }
  });
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    try {
      return window.localStorage.getItem("second_brain_authenticated") === "true";
    } catch {
      return false;
    }
  });
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [activeSection, setActiveSection] = useState("dashboard");
  const [questionLoading, setQuestionLoading] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [analytics, setAnalytics] = useState({
    total_questions: 0,
    documents_uploaded: 0,
    due_flashcards: 0,
    topics: {},
    study_recommendations: { weak_topics: [], recommendation: "" },
    recent_documents: [],
    system_status: { ready: false, warnings: [] },
  });
  const [pdfFile, setPdfFile] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [youtubeTranscript, setYoutubeTranscript] = useState("");
  const [flashcards, setFlashcards] = useState([]);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [statusMessage, setStatusMessage] = useState("");
  const [language, setLanguage] = useState("english");
  const [theme, setTheme] = useState(() => {
    try {
      return window.localStorage.getItem("second_brain_theme") || "dark";
    } catch {
      return "dark";
    }
  });
  const [strictMode, setStrictMode] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("Ready");
  const [currentDocument, setCurrentDocument] = useState(null);
  const [notes, setNotes] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [activity, setActivity] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [coldStartNotice, setColdStartNotice] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [featureDrawerOpen, setFeatureDrawerOpen] = useState(false);
  const [actionMenuOpen, setActionMenuOpen] = useState(false);
  const chatFeedRef = useRef(null);
  const chatSectionRef = useRef(null);

  const profile = {
    name: authForm.name || "Your Name",
    plan: "Pro workspace",
    initials: (authForm.name || "YN")
      .split(" ")
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase(),
  };

  const topicData = Object.entries(analytics.topics || {}).map(([topic, count]) => ({
    topic,
    count,
  }));
  const systemStatus = analytics.system_status || { ready: false, warnings: [] };
  const recentDocuments = documents.length ? documents : analytics.recent_documents || [];
  const weakTopics = analytics.study_recommendations?.weak_topics || [];
  const topTopic = topicData.length
    ? [...topicData].sort((left, right) => right.count - left.count)[0]
    : null;
  const readinessScore = statusChecks.reduce(
    (score, check) => score + (systemStatus?.[check.key] ? 1 : 0),
    0,
  );
  const graphNodeNames = new Map((graph.nodes || []).map((node) => [node.id, node.name]));
  const graphConnections = (graph.edges || [])
    .slice(0, 5)
    .map((edge) => ({
      from: graphNodeNames.get(edge.source_node_id) || "Concept",
      to: graphNodeNames.get(edge.target_node_id) || "Concept",
      weight: edge.weight,
    }));
  const sourceCount = analytics.documents_uploaded ?? 0;
  const statCards = [
    { key: "notes", label: "Total Notes", value: notes.length, delta: `${notes.length ? "+ active" : "start today"}` },
    { key: "connections", label: "Connections", value: graph.edges?.length ?? 0, delta: graph.edges?.length ? "+ graph links" : "build graph" },
    { key: "tracked_topics", label: "Tags", value: topicData.length, delta: topicData.length ? "organized" : "add tags" },
    { key: "total_questions", label: "AI Queries", value: analytics.total_questions ?? 0, delta: "this month" },
  ];
  const todayLabel = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(new Date());
  const filteredNotes = notes.filter((note) => {
    const haystack = `${note.title} ${note.body} ${note.topic} ${(note.tags || []).join(" ")}`.toLowerCase();
    return haystack.includes(searchQuery.toLowerCase().trim());
  });
  const learningMissions = [
    {
      title: "Start guided learning",
      detail: currentDocument ? `Begin from ${currentDocument.title}` : "Upload a source to unlock a guided chapter flow.",
      cta: "Start",
      disabled: !currentDocument,
      prompt: "start from first topic of the pdf",
    },
    {
      title: "Practice weak area",
      detail: weakTopics[0] ? `Focus recommendation: ${weakTopics[0]}` : "Ask a few questions so weak topics can be detected.",
      cta: "Practice",
      disabled: !weakTopics[0],
      prompt: weakTopics[0] ? `Create a practice quiz for ${weakTopics[0]} with answers after each question.` : "",
    },
    {
      title: "Visual explanation",
      detail: topTopic ? `Turn ${topTopic.topic} into a mini diagram and example.` : "Build visual explanations from uploaded content.",
      cta: "Visualize",
      disabled: !topTopic && !currentDocument,
      prompt: topTopic
        ? `Explain ${topTopic.topic} with a mini diagram, example, and revision points.`
        : "Explain the active uploaded source with a mini diagram.",
    },
  ];
  const youtubeModeLabel = youtubeTranscript.trim()
    ? "Manual transcript mode"
    : "Automatic captions mode";

  const jumpToSection = (sectionId) => {
    const target = document.getElementById(sectionId);
    const isSidebarTarget = Boolean(target?.closest(".sidebar-panel"));
    const isMobileViewport = window.matchMedia?.("(max-width: 1024px)")?.matches;

    setActiveSection(sectionId);
    setMobileSidebarOpen(Boolean(isSidebarTarget && isMobileViewport));
    setFeatureDrawerOpen(false);
    setActionMenuOpen(false);
    window.requestAnimationFrame(() => {
      document.getElementById(sectionId)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
        inline: "nearest",
      });
    });
  };

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem("second_brain_theme", theme);
    } catch {
      // Theme persistence is optional.
    }
  }, [theme]);

  useEffect(() => {
    document.body.classList.toggle("mobile-sidebar-open", mobileSidebarOpen);
    return () => document.body.classList.remove("mobile-sidebar-open");
  }, [mobileSidebarOpen]);

  const withColdStartNotice = async (requestPromise) => {
    const timer = window.setTimeout(() => setColdStartNotice(true), 3000);
    try {
      return await requestPromise;
    } finally {
      window.clearTimeout(timer);
      setColdStartNotice(false);
    }
  };

  const validateUploadFile = (file, allowedTypes, label) => {
    if (!file) return false;
    if (file.size > MAX_UPLOAD_BYTES) {
      setStatusMessage(`${label} is too large. Maximum upload size is 20MB.`);
      return false;
    }
    if (allowedTypes.size && !allowedTypes.has(file.type)) {
      setStatusMessage(`Unsupported ${label.toLowerCase()} type. Use PDF, PNG, JPG, or WebP as appropriate.`);
      return false;
    }
    return true;
  };

  useEffect(() => {
    const sections = sidebarSections
      .map((section) => document.getElementById(section.id))
      .filter(Boolean);

    if (!sections.length) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];

        if (visible?.target?.id) {
          setActiveSection(visible.target.id);
        }
      },
      { rootMargin: "-20% 0px -55% 0px", threshold: [0.2, 0.5, 0.8] },
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  const loadSidebarData = async () => {
    try {
      const [analyticsRes, dueFlashcardsRes, graphRes, recommendationsRes, notesRes, activityRes, documentsRes] = await Promise.all([
        api.get("/analytics"),
        api.get("/study/flashcards/due"),
        api.get("/graph"),
        api.get("/recommendations"),
        api.get("/notes"),
        api.get("/activity"),
        api.get("/documents"),
      ]);

      setAnalytics(unwrapPayload(analyticsRes.data));
      setFlashcards(unwrapPayload(dueFlashcardsRes.data).flashcards || dueFlashcardsRes.data.flashcards || []);
      setGraph(unwrapPayload(graphRes.data) || { nodes: [], edges: [] });
      setRecommendations(unwrapPayload(recommendationsRes.data).recommendations || []);
      setNotes(unwrapPayload(notesRes.data).notes || []);
      setActivity(unwrapPayload(activityRes.data).events || []);
      const loadedDocuments = unwrapPayload(documentsRes.data).documents || documentsRes.data.documents || [];
      setDocuments(loadedDocuments);
      const latestDocument = loadedDocuments[0] || unwrapPayload(analyticsRes.data)?.recent_documents?.[0];
      if (latestDocument && !currentDocument) {
        setCurrentDocument({ id: latestDocument.id, title: latestDocument.title });
      }
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Failed to load dashboard data.");
    }
  };

  const refreshSidebarInBackground = async () => {
    try {
      await loadSidebarData();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Uploaded successfully, but dashboard refresh is still catching up.");
    }
  };

  const loadDashboard = async () => {
    setDashboardLoading(true);
    try {
      const historyRes = await api.get("/history");
      const historyPayload = unwrapPayload(historyRes.data);
      setMessages(historyPayload.messages || historyRes.data.messages || []);
      await loadSidebarData();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Failed to load dashboard data.");
    } finally {
      setDashboardLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    // Dashboard bootstrap should run once for the current browser session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const feed = chatFeedRef.current;
    if (!feed) return;
    feed.scrollTo({ top: feed.scrollHeight, behavior: "smooth" });
  }, [messages, questionLoading]);

  const openChat = () => {
    window.requestAnimationFrame(() => {
      chatSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const askQuestion = async (questionOverride) => {
    const currentQuestion = typeof questionOverride === "string" ? questionOverride.trim() : input.trim();
    if (!currentQuestion) return;
    const fallbackDocument = currentDocument || recentDocuments[0] || null;

    setMessages((prev) => [...prev, { role: "user", text: currentQuestion, createdAt: new Date().toISOString() }]);
    setInput("");
    setQuestionLoading(true);
    setStatusMessage("");
    openChat();

    try {
      const response = await withColdStartNotice(api.post("/ask", {
        question: currentQuestion,
        source: "all",
        language,
        document_id: fallbackDocument?.id ?? null,
        user_id: sessionId,
        strict: strictMode,
      }));
      const answerPayload = unwrapPayload(response.data);
      const safeAnswer = normalizeAssistantText(answerPayload.answer);
      if (answerPayload.document_id) {
        setCurrentDocument({
          id: answerPayload.document_id,
          title: answerPayload.document_title || currentDocument?.title || "active document",
        });
      }
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: safeAnswer,
          createdAt: new Date().toISOString(),
          topic: answerPayload.topic,
          sources: answerPayload.sources || [],
          language: answerPayload.language,
          documentId: answerPayload.document_id,
          documentTitle: answerPayload.document_title,
        },
      ]);
      await loadSidebarData();
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: error.response?.data?.detail || "The assistant could not answer right now.",
          createdAt: new Date().toISOString(),
          topic: "System",
        },
      ]);
    } finally {
      setQuestionLoading(false);
    }
  };

  const runQuickAction = (action) => {
    const prompt = action.buildPrompt(input.trim());
    setInput(prompt);
    if (action.label === "Next") {
      askQuestion(prompt);
    }
  };

  const runMission = (mission) => {
    if (mission.disabled || !mission.prompt) return;
    askQuestion(mission.prompt);
  };

  const clearHistory = async () => {
    try {
      await api.delete("/history");
      setMessages([]);
      await loadDashboard();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Unable to clear chat history.");
    }
  };

  const selectDocument = async (document) => {
    setCurrentDocument({ id: document.id, title: document.title });
    try {
      const response = await api.get(`/documents/${document.id}`);
      const payload = unwrapPayload(response.data);
      setStatusMessage(`Active source: ${payload.title}. ${payload.character_count || 0} characters indexed.`);
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || `Active source: ${document.title}`);
    }
  };

  const deleteSource = async (document, event) => {
    event.stopPropagation();
    const confirmed = window.confirm(`Delete "${document.title}" from this workspace?`);
    if (!confirmed) return;

    try {
      await api.delete(`/documents/${document.id}`);
      setDocuments((prev) => prev.filter((item) => item.id !== document.id));
      if (currentDocument?.id === document.id) {
        setCurrentDocument(null);
      }
      setStatusMessage(`Deleted source: ${document.title}`);
      await loadSidebarData();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Could not delete source.");
    }
  };

  const saveComposerAsNote = async () => {
    const body = input.trim();
    if (!body) return;

    const title = body.split("\n")[0].slice(0, 90) || "Untitled note";
    try {
      const response = await api.post("/notes", {
        title,
        body,
        topic: currentDocument?.title || "General",
        tags: currentDocument ? ["Source note"] : ["Quick note"],
        user_id: sessionId,
      });
      const note = unwrapPayload(response.data);
      setNotes((prev) => [note, ...prev]);
      setInput("");
      setStatusMessage("Saved note to your knowledge workspace.");
      await loadSidebarData();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Could not save note.");
    }
  };

  const runRecommendation = (recommendation) => {
    if (!recommendation?.action_prompt) return;
    askQuestion(recommendation.action_prompt);
  };

  const uploadPdf = async (selectedFile = pdfFile) => {
    if (!selectedFile) return;
    if (!validateUploadFile(selectedFile, PDF_TYPES, "PDF")) return;

    const formData = new FormData();
    formData.append("file", selectedFile);
    setUploadLoading(true);
    setUploadStatus(`Uploading ${selectedFile.name}...`);
    setStatusMessage("");

    try {
      const response = await withColdStartNotice(api.post("/upload-pdf", formData, {
        timeout: UPLOAD_TIMEOUT_MS,
      }));
      const payload = unwrapPayload(response.data);
      const title = payload.title || response.data.title || selectedFile.name || "uploaded document";
      setStatusMessage(`Indexed PDF: ${title}`);
      setCurrentDocument({ id: payload.document_id, title });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `PDF indexed: ${title}\n\nYou can ask questions from this source now. Try "summarize this PDF" or "teach me the first topic".`,
          createdAt: new Date().toISOString(),
          topic: "upload",
          documentId: payload.document_id,
          documentTitle: title,
        },
      ]);
      setPdfFile(null);
      setUploadLoading(false);
      setUploadStatus("Refreshing dashboard...");
      void refreshSidebarInBackground().finally(() => setUploadStatus("Ready"));
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "PDF upload failed.");
      setUploadStatus("Ready");
    } finally {
      setUploadLoading(false);
    }
  };

  const uploadYoutube = async () => {
    if (!youtubeUrl.trim()) return;

    setUploadLoading(true);
    setUploadStatus("Indexing YouTube...");
    setStatusMessage("");

    try {
      const response = await withColdStartNotice(api.post(
        "/upload-youtube",
        {
          url: youtubeUrl.trim(),
          transcript: youtubeTranscript.trim() || undefined,
          title: youtubeTranscript.trim() ? `YouTube notes: ${youtubeUrl.trim()}` : undefined,
          user_id: sessionId,
        },
        { timeout: UPLOAD_TIMEOUT_MS },
      ));
      const payload = unwrapPayload(response.data);
      const title = payload.title || response.data.title || youtubeUrl.trim();
      setStatusMessage(`Indexed YouTube source: ${title}`);
      setCurrentDocument({ id: payload.document_id, title });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `YouTube source indexed: ${title}\n\nAsk for a summary, key ideas, or a study flow from this source.`,
          createdAt: new Date().toISOString(),
          topic: "upload",
          documentId: payload.document_id,
          documentTitle: title,
        },
      ]);
      setYoutubeUrl("");
      setYoutubeTranscript("");
      setUploadLoading(false);
      setUploadStatus("Refreshing dashboard...");
      void refreshSidebarInBackground().finally(() => setUploadStatus("Ready"));
    } catch (error) {
      const detail = error.response?.data?.detail || "YouTube ingestion failed.";
      setStatusMessage(`${detail} Paste the transcript below to index it manually.`);
      setUploadStatus("Ready");
    } finally {
      setUploadLoading(false);
    }
  };

  const uploadImage = async (selectedFile = imageFile) => {
    if (!selectedFile) return;
    if (!validateUploadFile(selectedFile, IMAGE_TYPES, "Image")) return;

    const formData = new FormData();
    formData.append("file", selectedFile);
    setUploadLoading(true);
    setUploadStatus(`Reading ${selectedFile.name}...`);
    setStatusMessage("");

    try {
      const response = await withColdStartNotice(api.post("/upload-image", formData, {
        timeout: UPLOAD_TIMEOUT_MS,
      }));
      const payload = unwrapPayload(response.data);
      if (payload.warning || response.data.warning) {
        setStatusMessage(payload.warning || response.data.warning);
      } else if (payload.text || response.data.text) {
        setStatusMessage(`OCR done. Extracted text preview: ${(payload.text || response.data.text).slice(0, 140)}`);
      } else if (payload.text_preview || response.data.text_preview) {
        setStatusMessage(`Image indexed. OCR preview: ${(payload.text_preview || response.data.text_preview).slice(0, 140)}`);
      } else {
        setStatusMessage("Image processed, but no readable text was found.");
      }
      const title = payload.title || response.data.title || selectedFile.name || "uploaded image";
      setCurrentDocument({ id: payload.document_id, title });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Image indexed: ${title}\n\nOCR text is ready. Ask me to explain, summarize, or turn it into revision notes.`,
          createdAt: new Date().toISOString(),
          topic: "upload",
          documentId: payload.document_id,
          documentTitle: title,
        },
      ]);
      setImageFile(null);
      setUploadLoading(false);
      setUploadStatus("Refreshing dashboard...");
      void refreshSidebarInBackground().finally(() => setUploadStatus("Ready"));
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Image upload failed.");
      setUploadStatus("Ready");
    } finally {
      setUploadLoading(false);
    }
  };

  const generateFlashcards = async () => {
    try {
      const response = await withColdStartNotice(api.post("/study/flashcards", { limit: 5, user_id: sessionId }));
      const payload = unwrapPayload(response.data);
      setFlashcards(payload.flashcards || response.data.flashcards || []);
      setStatusMessage("Generated new flashcards. They are ready for review now.");
      await loadDashboard();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Could not generate flashcards.");
    }
  };

  const reviewFlashcard = async (cardId, quality) => {
    try {
      await api.post(`/study/flashcards/${cardId}/review`, { quality });
      await loadDashboard();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Could not review the flashcard.");
    }
  };

  const handleEnter = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      askQuestion();
    }
  };

  const handleAuthSubmit = (event) => {
    event.preventDefault();
    const name = authForm.name.trim() || "Learner";
    const email = authForm.email.trim();
    setAuthForm({ name, email });
    try {
      window.localStorage.setItem("second_brain_authenticated", "true");
      window.localStorage.setItem("second_brain_user_name", name);
      window.localStorage.setItem("second_brain_user_email", email);
    } catch {
      // Local auth state is only for the product preview experience.
    }
    setIsAuthenticated(true);
  };

  const signOut = () => {
    try {
      window.localStorage.removeItem("second_brain_authenticated");
    } catch {
      // Ignore storage failures.
    }
    setIsAuthenticated(false);
  };

  const launcherActions = [
    { label: "Upload PDF or image", text: "Add chapters, notes, screenshots, or scanned pages.", action: () => jumpToSection("upload") },
    { label: "Add YouTube video", text: "Index captions or paste a transcript fallback.", action: () => jumpToSection("upload") },
    { label: "Ask from sources", text: "Summaries, explanations, comparisons, and citations.", action: () => jumpToSection("chat") },
    { label: "Create notes", text: "Save ideas and connect them to your knowledge base.", action: () => jumpToSection("notes") },
    { label: "Study mode", text: "Flashcards, weak topics, and revision missions.", action: () => jumpToSection("study") },
    { label: "Knowledge graph", text: "See concepts and how your sources connect.", action: () => jumpToSection("graph") },
  ];

  const quickStartActions = [
    { label: "Summarize", prompt: "Summarize my active source with key points, examples, and revision notes." },
    { label: "Teach", prompt: "Teach my active source step by step in simple language." },
    { label: "Practice", prompt: "Create practice questions and flashcards from my active source." },
  ];

  if (!isAuthenticated) {
    return (
      <div className="auth-shell">
        <section className="auth-hero">
          <div className="auth-copy">
            <p className="eyebrow">Second Brain AI</p>
            <h1>Understand every source faster.</h1>
            <p>
              Sign in to organize PDFs, screenshots, YouTube transcripts, notes, flashcards,
              and AI answers inside one focused study workspace.
            </p>
            <div className="auth-benefits">
              <span>PDF tutor</span>
              <span>YouTube notes</span>
              <span>Flashcards</span>
              <span>Knowledge graph</span>
            </div>
          </div>
          <form className="auth-card" onSubmit={handleAuthSubmit}>
            <div>
              <h2>Welcome back</h2>
              <p>Use any name and email to preview the workspace.</p>
            </div>
            <label>
              <span>Name</span>
              <input
                value={authForm.name}
                onChange={(event) => setAuthForm((prev) => ({ ...prev, name: event.target.value }))}
                placeholder="Ram Arora"
              />
            </label>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={authForm.email}
                onChange={(event) => setAuthForm((prev) => ({ ...prev, email: event.target.value }))}
                placeholder="you@example.com"
              />
            </label>
            <button className="primary-button" type="submit">
              Enter workspace
            </button>
            <small>Preview auth only. Backend user accounts can be connected later.</small>
          </form>
        </section>
      </div>
    );
  }

  return (
    <div className="app-shell app-root">
      <button
        className="feature-side-button"
        onClick={() => setFeatureDrawerOpen((prev) => !prev)}
        type="button"
        aria-label="Open feature launcher"
      >
        Features
      </button>

      {featureDrawerOpen && (
        <aside className="feature-drawer" aria-label="Feature launcher">
          <div className="feature-drawer-head">
            <div>
              <span>Workspace menu</span>
              <h2>What do you want to do?</h2>
            </div>
            <button className="tiny-button" onClick={() => setFeatureDrawerOpen(false)} type="button">
              Close
            </button>
          </div>
          <div className="feature-action-list">
            {launcherActions.map((item) => (
              <button className="feature-action" key={item.label} onClick={item.action} type="button">
                <strong>{item.label}</strong>
                <span>{item.text}</span>
              </button>
            ))}
          </div>
          <button className="ghost-button" onClick={signOut} type="button">
            Sign out
          </button>
        </aside>
      )}

      <div className="bottom-chat-dock">
        <button
          className="dock-plus-button"
          onClick={() => setActionMenuOpen((prev) => !prev)}
          type="button"
          aria-label="Open quick actions"
        >
          +
        </button>
        {actionMenuOpen && (
          <div className="dock-action-popover">
            <button onClick={() => jumpToSection("upload")} type="button">Add source</button>
            <button onClick={() => jumpToSection("study")} type="button">Study tools</button>
            <button onClick={() => jumpToSection("notes")} type="button">Notes</button>
            <button onClick={() => jumpToSection("graph")} type="button">Graph</button>
          </div>
        )}
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleEnter}
          placeholder="Ask anything from your sources..."
        />
        <button
          className="dock-send-button"
          onClick={() => askQuestion()}
          disabled={questionLoading || !input.trim()}
          type="button"
        >
          Send
        </button>
        <div className="dock-quick-row">
          {quickStartActions.map((action) => (
            <button
              key={action.label}
              onClick={() => {
                setInput(action.prompt);
                jumpToSection("chat");
              }}
              type="button"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      <button
        className="mobile-menu-button"
        onClick={() => setMobileSidebarOpen(true)}
        type="button"
        aria-label="Open workspace sidebar"
      >
        Menu
      </button>
      {mobileSidebarOpen && (
        <button
          className="mobile-sidebar-backdrop"
          onClick={() => setMobileSidebarOpen(false)}
          type="button"
          aria-label="Close workspace sidebar"
        />
      )}
      <nav className="mobile-bottom-nav" aria-label="Mobile workspace navigation">
        {railSections.map((section) => (
          <a
            className={`mobile-tab ${activeSection === section.id ? "active" : ""}`}
            href={`#${section.id}`}
            key={section.id}
            onClick={(event) => {
              event.preventDefault();
              jumpToSection(section.id);
            }}
          >
            <span>{section.short}</span>
            <small>{section.label}</small>
          </a>
        ))}
      </nav>
      <div className="app-layout">
        <aside className="rail-panel">
          <div className="rail-brand">SB</div>
          <div className="rail-stack">
            {railSections.map((section) => (
              <a
                className={`rail-link ${activeSection === section.id ? "active" : ""}`}
                href={`#${section.id}`}
                key={section.id}
                onClick={(event) => {
                  event.preventDefault();
                  jumpToSection(section.id);
                }}
                title={section.label}
              >
                <span className="rail-badge">{section.short}</span>
                <small>{section.label}</small>
              </a>
            ))}
          </div>
          <button className="rail-profile" onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}>
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </aside>

        <aside className={`glass-panel sidebar-panel ${mobileSidebarOpen ? "open" : ""}`}>
          <div className="brand-block">
            <div className="brand-mark">SB</div>
            <div>
              <h1 className="panel-title">Second Brain</h1>
              <p className="section-copy">AI-powered memory</p>
            </div>
          </div>

          <label className="search-box">
            <span>Search</span>
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search everything..."
            />
          </label>

          <nav className="section-nav">
            {sidebarSections.map((section) => (
              <a
                className={`nav-link ${activeSection === section.id ? "active" : ""}`}
                href={`#${section.id}`}
                key={section.id}
                onClick={(event) => {
                  event.preventDefault();
                  jumpToSection(section.id);
                }}
              >
                <span className="nav-icon">{navMeta[section.id]?.icon}</span>
                <span>{section.label}</span>
                {navMeta[section.id]?.count === "notes" && <small>{notes.length}</small>}
              </a>
            ))}
          </nav>

          <div className="section-block section-block-tight">
            <div className="section-head">
              <h2>Response Mode</h2>
              <span>{language === "hinglish" ? "Hinglish" : "English"}</span>
            </div>
            <div className="toggle-row">
              <button
                className={`toggle-chip ${language === "english" ? "active" : ""}`}
                onClick={() => setLanguage("english")}
              >
                English
              </button>
              <button
                className={`toggle-chip ${language === "hinglish" ? "active" : ""}`}
                onClick={() => setLanguage("hinglish")}
              >
                Hinglish
              </button>
            </div>
            <div className="toggle-row mode-toggle-row">
              <button
                className={`toggle-chip ${strictMode ? "active" : ""}`}
                onClick={() => setStrictMode((prev) => !prev)}
              >
                Strict sources {strictMode ? "On" : "Off"}
              </button>
            </div>
          </div>

          <div className={`section-block section-block-tight status-panel ${systemStatus.ready ? "status-ok" : "status-warning"}`}>
            <div className="section-head">
              <h2>System Status</h2>
              <span>{readinessScore}/{statusChecks.length} ready</span>
            </div>
            <p className="section-copy">
              {systemStatus.ready
                ? "Your learning engine is online: chat, retrieval, uploads, and analytics can work together."
                : "This panel tells you exactly why a feature may feel weak before users get confused."}
            </p>
            <div className="readiness-list">
              {statusChecks.map((check) => {
                const ok = Boolean(systemStatus?.[check.key]);
                return (
                  <div className={`readiness-item ${ok ? "ready" : "blocked"}`} key={check.key}>
                    <span className="readiness-dot" />
                    <div>
                      <strong>{check.label}</strong>
                      <p>{ok ? check.ready : check.blocked}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            {(systemStatus.warnings || []).length > 0 && (
              <div className="warning-list">
                {systemStatus.warnings.slice(0, 4).map((warning) => (
                  <p className="warning-item" key={warning}>{warning}</p>
                ))}
              </div>
            )}
          </div>

          <div className="stats-grid">
            {statCards.map((card) => (
              <div className="stat-card" key={card.key}>
                <p className="stat-label">{card.label}</p>
                <p className="stat-value">
                  {dashboardLoading ? "..." : card.value}
                </p>
              </div>
            ))}
          </div>

          <div className="section-block compact-notes-panel">
            <div className="section-head">
              <h2>Notes</h2>
              <button className="ghost-button" onClick={saveComposerAsNote} disabled={!input.trim()}>
                Save
              </button>
            </div>
            <p className="section-copy">
              Capture durable ideas from chat, uploads, or your own thoughts.
            </p>
            <div className="document-list">
              {notes.length === 0 && (
                <EmptyHint
                  title="No notes yet"
                  text="Write an idea in the composer and save it as a structured note."
                />
              )}
              {notes.slice(0, 5).map((note) => (
                <button
                  className="note-item"
                  key={note.id}
                  onClick={() => askQuestion(`Connect this note to my knowledge base:\n${note.title}\n${note.body}`)}
                  type="button"
                >
                  <span>{note.title}</span>
                  <small>{note.topic} | {(note.tags || []).join(", ") || "General"}</small>
                </button>
              ))}
            </div>
          </div>

          <div className="section-block">
            <div className="section-head">
              <h2>Next Actions</h2>
              <span>{recommendations.length}</span>
            </div>
            <div className="mission-list">
              {recommendations.slice(0, 3).map((recommendation) => (
                <button
                  className="mission-card"
                  key={recommendation.id || recommendation.title}
                  onClick={() => runRecommendation(recommendation)}
                  type="button"
                >
                  <span>{recommendation.title}</span>
                  <small>{recommendation.reason}</small>
                  <strong>Run</strong>
                </button>
              ))}
            </div>
          </div>

          <div className="section-block" id="upload">
            <div className="section-head">
              <h2>Add Sources</h2>
              <span>{uploadLoading ? uploadStatus : uploadStatus}</span>
            </div>
            <p className="section-copy">
              Add one source first. After indexing, use Ask AI, Notes, Study Mode, and Graph from the same material.
            </p>
            {currentDocument && (
              <p className="section-copy">
                Active source: <strong>{currentDocument.title}</strong>
              </p>
            )}

            <label className="upload-field">
              <span>Upload PDF</span>
              <input
                type="file"
                accept="application/pdf"
                onChange={(event) => {
                  const file = event.target.files?.[0] || null;
                  const validFile = file && validateUploadFile(file, PDF_TYPES, "PDF") ? file : null;
                  setPdfFile(validFile);
                  if (validFile) {
                    void uploadPdf(validFile);
                    event.target.value = "";
                  }
                }}
                disabled={uploadLoading}
              />
            </label>
            {pdfFile && uploadLoading && <p className="status-text">Upload started automatically. The chat will stay focused while indexing finishes.</p>}

            <label className="upload-field">
              <span>Upload Image for OCR</span>
              <input
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0] || null;
                  const validFile = file && validateUploadFile(file, IMAGE_TYPES, "Image") ? file : null;
                  setImageFile(validFile);
                  if (validFile) {
                    void uploadImage(validFile);
                    event.target.value = "";
                  }
                }}
                disabled={uploadLoading}
              />
            </label>
            {imageFile && uploadLoading && <p className="status-text">OCR started automatically. You can stay in the chat while it works.</p>}

            <label className="upload-field">
              <span>YouTube URL</span>
              <input
                value={youtubeUrl}
                onChange={(event) => setYoutubeUrl(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
              />
            </label>
            <div className="youtube-mode-card">
              <div>
                <strong>{youtubeModeLabel}</strong>
                <p>
                  {youtubeTranscript.trim()
                    ? "The app will index the pasted transcript or notes directly."
                    : "The app will try YouTube captions first. If captions are blocked or missing, paste the transcript below."}
                </p>
              </div>
              <span>{youtubeTranscript.trim() ? `${youtubeTranscript.trim().length} chars` : "fallback ready"}</span>
            </div>
            <label className="upload-field">
              <span>Optional transcript fallback</span>
              <textarea
                value={youtubeTranscript}
                onChange={(event) => setYoutubeTranscript(event.target.value)}
                placeholder="If YouTube blocks automatic captions, paste the transcript or your video notes here..."
              />
            </label>
            <button className="secondary-button" onClick={uploadYoutube} disabled={!youtubeUrl.trim() || uploadLoading}>
              {uploadLoading ? uploadStatus : youtubeTranscript.trim() ? "Index pasted transcript" : "Try automatic captions"}
            </button>
          </div>

          <div className="section-block" id="study">
            <div className="section-head">
              <h2>Study Mode</h2>
              <button className="ghost-button" onClick={generateFlashcards}>
                Generate
              </button>
            </div>
            <p className="section-copy">
              {analytics.study_recommendations?.recommendation ||
                "This converts your uploads into a study plan, weak-topic practice, and revision cards."}
            </p>
            <div className="mission-list">
              {learningMissions.map((mission) => (
                <button
                  className="mission-card"
                  disabled={mission.disabled || questionLoading}
                  key={mission.title}
                  onClick={() => runMission(mission)}
                  type="button"
                >
                  <span>{mission.title}</span>
                  <small>{mission.detail}</small>
                  <strong>{mission.cta}</strong>
                </button>
              ))}
            </div>
            <div className="topic-row">
              {weakTopics.map((topic) => (
                <TopicPill topic={topic} key={topic} />
              ))}
            </div>
          </div>

          <div className="section-block" id="graph">
            <div className="section-head">
              <h2>Knowledge Graph</h2>
              <span>{graph.nodes.length} nodes</span>
            </div>
            {graph.nodes.length === 0 ? (
              <EmptyHint
                title="No graph yet"
                text="Upload a PDF, image, or YouTube source. The app will extract concepts and show how they connect."
              />
            ) : (
              <>
                <div className="concept-cloud">
                  {graph.nodes.slice(0, 10).map((node) => (
                    <button
                      className="concept-node"
                      key={node.id}
                      onClick={() => askQuestion(`Explain how ${node.name} connects to my uploaded material with an example.`)}
                      type="button"
                    >
                      <span>{node.name}</span>
                      <small>{node.weight}</small>
                    </button>
                  ))}
                </div>
                <div className="connection-list">
                  {graphConnections.map((edge) => (
                    <div className="connection-row" key={`${edge.from}-${edge.to}-${edge.weight}`}>
                      <span>{edge.from}</span>
                      <strong>connects to</strong>
                      <span>{edge.to}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="section-block">
            <div className="section-head">
              <h2>Recent Sources</h2>
              <span>{recentDocuments.length}</span>
            </div>
            <div className="document-list">
              {recentDocuments.length === 0 && (
                <p className="section-copy">Indexed sources will appear here after uploads.</p>
              )}
              {recentDocuments.slice(0, 8).map((document) => (
                <div
                  className={`document-item ${currentDocument?.id === document.id ? "active" : ""}`}
                  key={`${document.id}-${document.title}`}
                  onClick={() => selectDocument(document)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      selectDocument(document);
                    }
                  }}
                >
                  <div>
                    <p className="document-title">{document.title}</p>
                    <p className="document-meta">{document.source_type} | {document.topic}</p>
                  </div>
                  <div className="document-actions">
                    <button
                      className="tiny-button"
                      onClick={(event) => {
                        event.stopPropagation();
                        selectDocument(document);
                        askQuestion(`Summarize ${document.title} with key points and revision notes.`);
                      }}
                      type="button"
                    >
                      Ask
                    </button>
                    <button className="tiny-button danger" onClick={(event) => deleteSource(document, event)} type="button">
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="section-block">
            <div className="section-head">
              <h2>Activity</h2>
              <span>{activity.length}</span>
            </div>
            <div className="activity-list">
              {activity.length === 0 && (
                <p className="section-copy">Memory saves, uploads, notes, and study actions will appear here.</p>
              )}
              {activity.slice(0, 6).map((event) => (
                <div className="activity-item" key={event.id}>
                  <span>{event.event_type.replaceAll("_", " ")}</span>
                  <small>{event.metadata?.title || event.metadata?.topic || event.entity_type}</small>
                </div>
              ))}
            </div>
          </div>

          <div className="profile-card">
            <div className="profile-avatar">{profile.initials}</div>
            <div>
              <strong>{profile.name}</strong>
              <p>{profile.plan} · {notes.length} notes</p>
            </div>
          </div>
        </aside>

        <main className="main-layout">
          <header className="app-topbar">
            <div className="topbar-brand">
              <span className="topbar-logo">SB</span>
              <div>
                <strong>Second Brain</strong>
                <small>{currentDocument ? `Active source: ${currentDocument.title}` : "Personal AI study workspace"}</small>
              </div>
            </div>
            <div className="topbar-actions">
              <button className="ghost-button" onClick={() => setFeatureDrawerOpen(true)} type="button">
                Features
              </button>
              <button className="ghost-button" onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))} type="button">
                {theme === "dark" ? "Light" : "Dark"}
              </button>
              <button className="tiny-button" onClick={signOut} type="button">
                Sign out
              </button>
            </div>
          </header>
          <section className="dashboard-shell" id="dashboard">
            <div className="workspace-intro">
              <div className="intro-copy">
                <p className="eyebrow">AI study workspace</p>
                <h2 className="dashboard-title">One place to upload, understand, and revise your learning material.</h2>
                <p className="intro-text">
                  Second Brain turns PDFs, screenshots, YouTube transcripts, and notes into a personal tutor.
                  Users can ask questions, get summaries, create flashcards, find weak topics, and keep everything connected.
                </p>
                <div className="intro-actions">
                  <button className="primary-button" onClick={() => jumpToSection("upload")} type="button">
                    Start with upload
                  </button>
                  <button className="secondary-button" onClick={() => jumpToSection("chat")} type="button">
                    Ask a question
                  </button>
                  <button className="ghost-button" onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))} type="button">
                    {theme === "dark" ? "Light" : "Dark"}
                  </button>
                </div>
              </div>
              <div className="intro-status">
                <span>How it works</span>
                <div className="intro-step-list">
                  <p><strong>1</strong> Add material</p>
                  <p><strong>2</strong> Ask or summarize</p>
                  <p><strong>3</strong> Revise with notes and flashcards</p>
                </div>
                <small>{sourceCount} sources indexed · {currentDocument ? `Active: ${currentDocument.title}` : "No active source yet"}</small>
              </div>
            </div>

            <div className="capability-grid">
              {capabilityCards.map((card) => (
                <button
                  className="capability-card"
                  key={card.title}
                  onClick={() => jumpToSection(card.target)}
                  type="button"
                >
                  <span>{card.label}</span>
                  <strong>{card.title}</strong>
                  <p>{card.text}</p>
                  <small>{card.action}</small>
                </button>
              ))}
            </div>

            <section className="benefit-panel">
              <div className="benefit-panel-head">
                <div>
                  <p className="eyebrow">What users can do</p>
                  <h3>Everything useful is visible from the first screen.</h3>
                </div>
                <button className="ghost-button" onClick={() => jumpToSection("upload")} type="button">
                  Add first source
                </button>
              </div>
              <div className="benefit-grid">
                {benefitCards.map((benefit) => (
                  <div className="benefit-card" key={benefit.title}>
                    <strong>{benefit.title}</strong>
                    <p>{benefit.text}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="workflow-panel">
              <div className="workflow-copy">
                <p className="eyebrow">Try these workflows</p>
                <h3>Useful actions, not random buttons.</h3>
                <p>Pick a workflow after adding a source. The prompt goes straight into the AI workspace.</p>
              </div>
              <div className="workflow-list">
                {workflowCards.map((workflow) => (
                  <button
                    className="workflow-card"
                    key={workflow.title}
                    onClick={() => {
                      setInput(workflow.prompt);
                      jumpToSection("chat");
                    }}
                    type="button"
                  >
                    <strong>{workflow.title}</strong>
                    <span>{workflow.text}</span>
                  </button>
                ))}
              </div>
            </section>

            <div className="dashboard-stat-grid">
              {statCards.map((card) => (
                <div className="dashboard-stat-card" key={card.key}>
                  <strong>{dashboardLoading ? "..." : card.value}</strong>
                  <span>{card.label}</span>
                  <small>{card.delta}</small>
                </div>
              ))}
            </div>

            <div className="dashboard-content-grid">
              <section className="workspace-card" id="notes">
                <div className="workspace-card-header">
                  <h3>Recent Notes</h3>
                  <button className="ghost-button" onClick={() => setInput("New note idea: ")}>
                    Capture
                  </button>
                </div>
                <div className="recent-note-list">
                  {filteredNotes.length === 0 && (
                    <EmptyHint
                      title={notes.length ? "No matching notes" : "No notes yet"}
                      text={notes.length ? "Try another search term." : "Write in the composer, then save it as your first note."}
                    />
                  )}
                  {filteredNotes.slice(0, 4).map((note, index) => (
                    <button
                      className="recent-note-card"
                      key={note.id}
                      onClick={() => askQuestion(`Connect this note to my knowledge base:\n${note.title}\n${note.body}`)}
                      type="button"
                    >
                      <span className={`note-accent accent-${index % 4}`} />
                      <div>
                        <strong>{note.title}</strong>
                        <p>{note.body || "No body yet"}</p>
                        <div className="note-tags">
                          {(note.tags || ["General"]).slice(0, 2).map((tag) => (
                            <small key={tag}>{tag}</small>
                          ))}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </section>

              <section className="workspace-card">
                <div className="workspace-card-header">
                  <h3>Recent Activity</h3>
                  <span>{activity.length}</span>
                </div>
                <div className="timeline-list">
                  {activity.length === 0 && (
                    <EmptyHint
                      title="No activity yet"
                      text="Uploads, saved memories, notes, and AI answers will show up here."
                    />
                  )}
                  {activity.slice(0, 5).map((event, index) => (
                    <div className="timeline-item" key={event.id}>
                      <span className={`timeline-dot accent-${index % 4}`} />
                      <div>
                        <strong>{event.event_type.replaceAll("_", " ")}</strong>
                        <p>{event.metadata?.title || event.metadata?.topic || event.entity_type}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="weekly-goal">
                  <div>
                    <span>Weekly goal</span>
                    <strong>{Math.min(notes.length, 15)} / 15</strong>
                  </div>
                  <div className="goal-track">
                    <span style={{ width: `${Math.min((notes.length / 15) * 100, 100)}%` }} />
                  </div>
                </div>
              </section>
            </div>

            <section className="workspace-card feature-strip">
              <div>
                <h3>Features</h3>
                <p>Memory, notes, uploads, graph, strict source answers, and study recommendations now live in one workspace.</p>
              </div>
              <button className="secondary-button" onClick={clearHistory}>
                Clear Chat
              </button>
            </section>
          </section>

          <section className="glass-panel chat-panel" id="chat" ref={chatSectionRef}>
            <div className="chat-hero">
              <div className="chat-hero-copy">
                <p className="eyebrow">AI Knowledge Engine</p>
                <h2 className="panel-title">Not just chat. A study OS for your uploaded knowledge.</h2>
                <p className="section-copy">
                  It remembers your sources, builds concept maps, detects weak topics, schedules flashcards, and answers with citations from your material.
                </p>
              </div>
              <div className="chat-hero-status">
                <div className="hero-status-card">
                  <span className="status-dot" />
                  <div>
                    <strong>{questionLoading ? "Thinking..." : "Ready"}</strong>
                    <p>{language === "hinglish" ? "Hinglish mode enabled" : "English mode enabled"}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="value-grid">
              <div className="value-card">
                <span>01</span>
                <strong>Source-grounded answers</strong>
                <p>Answers come from uploaded PDFs, OCR images, YouTube transcripts, and recent memory.</p>
              </div>
              <div className="value-card">
                <span>02</span>
                <strong>Learning workflow</strong>
                <p>Start topics, move next, revise, summarize, and generate flashcards from the same source.</p>
              </div>
              <div className="value-card">
                <span>03</span>
                <strong>Personal progress</strong>
                <p>Analytics, weak-topic detection, due cards, and graph concepts show what to study next.</p>
              </div>
            </div>

            <div className="quick-actions">
              {quickActions.map((action) => (
                <button
                  className="quick-action-button"
                  key={action.label}
                  onClick={() => runQuickAction(action)}
                  disabled={questionLoading}
                >
                  {action.label}
                </button>
              ))}
            </div>

            <div className="chat-feed" ref={chatFeedRef}>
              {messages.length === 0 && (
                <div className="empty-state">
                  <p className="empty-title">Your knowledge workspace is ready.</p>
                  <p className="empty-copy">
                    Upload a PDF or YouTube transcript, then ask for summaries, explanations, or revision help.
                  </p>
                  <div className="starter-grid">
                    {starterPrompts.map((prompt) => (
                      <button
                        className="starter-card"
                        key={prompt}
                        onClick={() => setInput(prompt)}
                        type="button"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((message, index) => (
                <div className={`message-shell ${message.role}`} key={`${message.role}-${index}`}>
                  <div className="message-card">
                    <MessageBody text={message.text} />
                  </div>
                  <small className="message-time">{formatMessageTime(message.createdAt)}</small>
                  {message.role === "assistant" && (
                    <div className="message-meta">
                      <TopicPill topic={message.topic} />
                      <span className="source-chip">
                        {message.language === "hinglish" ? "Hinglish" : "English"}
                      </span>
                      {(message.sources || []).slice(0, 2).map((source) => (
                        <span className="source-chip" key={`${source.chunk_id}-${source.score}`}>
                          Source: {source.metadata?.title || source.metadata?.source_type}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {questionLoading && (
                <div className="message-shell assistant">
                  <div className="message-card thinking-card">
                    <div className="thinking-dots" aria-label="Thinking">
                      <span />
                      <span />
                      <span />
                    </div>
                    <p className="thinking-text">{language === "hinglish" ? "Soch raha hoon..." : "Thinking through your context..."}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="composer">
              <textarea
                className="composer-input"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleEnter}
                placeholder={
                  language === "hinglish"
                    ? "Koi concept poochho, summary maango, ya revision help lo..."
                    : "Ask a concept, request a summary, or generate revision help..."
                }
              />
              <button className="primary-button composer-button" onClick={askQuestion} disabled={questionLoading || !input.trim()}>
                {language === "hinglish" ? "Poochho" : "Send"}
              </button>
            </div>
            {coldStartNotice && (
              <p className="status-text wakeup-text">
                Waking up the server. First request on a free host can take around 30 seconds.
              </p>
            )}
            {statusMessage && <p className="status-text">{statusMessage}</p>}
          </section>

          <section className="bottom-grid">
            <div className="glass-panel">
              <div className="section-head">
                <h2>Topic Analytics</h2>
                <span>{topicData.length} tracked topics</span>
              </div>
              <div className="chart-grid">
                <div className="chart-card">
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={topicData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#314158" />
                      <XAxis dataKey="topic" stroke="#9db4d2" />
                      <YAxis stroke="#9db4d2" />
                      <Tooltip />
                      <Bar dataKey="count" fill="var(--accent)" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="chart-card">
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Pie data={topicData} dataKey="count" nameKey="topic" outerRadius={80} fill="var(--accent)" />
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <div className="glass-panel">
              <div className="section-head">
                <h2>Due Flashcards</h2>
                <span>{flashcards.length}</span>
              </div>
              <div className="flashcard-list">
                {flashcards.length === 0 && (
                  <EmptyHint
                    title="No cards due"
                    text={
                      sourceCount
                        ? "Generate cards from your sources. New cards are scheduled for later, like real spaced repetition."
                        : "Upload study material first, then generate flashcards from real chunks."
                    }
                    action={sourceCount ? "Generate flashcards" : undefined}
                    onClick={generateFlashcards}
                  />
                )}
                {flashcards.map((card) => (
                  <div className="flashcard" key={card.id}>
                    <TopicPill topic={card.topic} />
                    <p className="flashcard-question">{card.question}</p>
                    <p className="flashcard-answer">{card.answer}</p>
                    <div className="flashcard-actions">
                      <button className="ghost-button" onClick={() => reviewFlashcard(card.id, 2)}>
                        Hard
                      </button>
                      <button className="ghost-button" onClick={() => reviewFlashcard(card.id, 4)}>
                        Good
                      </button>
                      <button className="ghost-button" onClick={() => reviewFlashcard(card.id, 5)}>
                        Easy
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

