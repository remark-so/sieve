import { useMemo, useState } from "react";
import { MessagesSquare, SearchX, Sparkles } from "lucide-react";
import { Badge } from "@/components/arc/badge/badge";
import { EmptyState } from "@/components/arc/empty-state/empty-state";
import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { SearchField } from "@/components/arc/search-field/search-field";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { SortableDataTable } from "@/components/arc/sortable-data-table/sortable-data-table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/arc/tabs/tabs";
import { data, type Conversation, type Learning } from "./data";
import styles from "./App.module.css";

const dateFormat = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

function formatDate(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : `${iso}Z`);
  return Number.isNaN(d.getTime()) ? iso : dateFormat.format(d);
}

function matches(query: string, ...fields: string[]) {
  const q = query.trim().toLowerCase();
  return !q || fields.some((f) => f.toLowerCase().includes(q));
}

type LearningRow = Learning & { support: number } & Record<string, unknown>;
type ConversationRow = Conversation & Record<string, unknown>;

function LearningsPanel({ rows }: { rows: LearningRow[] }) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const visible = rows.filter((r) => (kind === "all" || r.type === kind) && matches(query, r.learning, r.why, r.id));

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<Sparkles size={24} />}
        title="No learnings yet"
        description="Run /sieve in this repository to read its conversations."
      />
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <SearchField label="Search learnings" value={query} onValueChange={setQuery} className={styles.search} />
        <SegmentedControl
          label="Type"
          value={kind}
          onValueChange={setKind}
          options={[
            { value: "all", label: "All" },
            { value: "rule", label: "Rules" },
            { value: "insight", label: "Insights" },
          ]}
        />
      </div>
      {visible.length === 0 ? (
        <EmptyState icon={<SearchX size={24} />} title="No matches" description="Try other words or show all types." />
      ) : (
        <SortableDataTable<LearningRow>
          rows={visible}
          rowKey="id"
          caption="Learnings"
          itemName={{ one: "learning", other: "learnings" }}
          defaultSort={{ key: "updated", direction: "desc" }}
          columns={[
            { key: "type", label: "Type", width: 104, render: (v) => <Badge size="sm" tone={v === "rule" ? "info" : "success"}>{v === "rule" ? "Rule" : "Insight"}</Badge> },
            {
              key: "learning",
              label: "Learning",
              render: (_, row) => (
                <div className={styles.learning}>
                  <span>{row.learning}</span>
                  {row.why ? <span className={styles.why}>{row.why}</span> : null}
                </div>
              ),
            },
            { key: "support", label: "Conversations", width: 140, numeric: true },
            { key: "updated", label: "Updated", width: 136, render: (v) => <span className={styles.nowrap}>{formatDate(String(v))}</span> },
            { key: "id", label: "ID", width: 96, sortable: false, render: (v) => <code className={styles.id}>{String(v)}</code> },
          ]}
        />
      )}
    </div>
  );
}

function ConversationsPanel({ rows }: { rows: ConversationRow[] }) {
  const [query, setQuery] = useState("");
  const visible = rows.filter((r) => matches(query, r.summary, r.who, r.conversation));

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<MessagesSquare size={24} />}
        title="No conversations logged"
        description="Run /sieve in this repository to log its conversations."
      />
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <SearchField label="Search conversations" value={query} onValueChange={setQuery} className={styles.search} />
      </div>
      {visible.length === 0 ? (
        <EmptyState icon={<SearchX size={24} />} title="No matches" description="Try other words." />
      ) : (
        <SortableDataTable<ConversationRow>
          rows={visible}
          rowKey="conversation"
          caption="Conversations"
          itemName={{ one: "conversation", other: "conversations" }}
          defaultSort={{ key: "date", direction: "desc" }}
          columns={[
            { key: "date", label: "Date", width: 136, render: (v) => <span className={styles.nowrap}>{formatDate(String(v))}</span> },
            { key: "who", label: "Who", width: 160 },
            { key: "summary", label: "Summary", render: (v) => <span className={styles.summary}>{String(v)}</span> },
            { key: "conversation", label: "ID", width: 112, sortable: false, render: (v) => <code className={styles.id}>{String(v)}</code> },
          ]}
        />
      )}
    </div>
  );
}

export function App() {
  const learnings = useMemo<LearningRow[]>(
    () => data.learnings.map((l) => ({ ...l, support: l.conversations.length })),
    [],
  );
  const conversations = data.conversations as ConversationRow[];
  const rules = learnings.filter((l) => l.type === "rule").length;
  const name = data.repo.split("/").filter(Boolean).pop() ?? data.repo;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>{name}</h1>
        <p className={styles.meta}>
          {data.lastRun ? `Learnings from Claude Code conversations · last read ${formatDate(data.lastRun)}` : "Learnings from Claude Code conversations"}
        </p>
      </header>

      <section className={styles.metrics} aria-label="Summary">
        <MetricCard label="Rules" value={rules} context="To follow" />
        <MetricCard label="Insights" value={learnings.length - rules} context="Learned" />
        <MetricCard label="Conversations" value={conversations.length} context="Logged" />
      </section>

      <Tabs defaultValue="learnings">
        <TabsList aria-label="Sieve">
          <TabsTrigger value="learnings">Learnings</TabsTrigger>
          <TabsTrigger value="conversations">Conversations</TabsTrigger>
        </TabsList>
        <TabsContent value="learnings">
          <LearningsPanel rows={learnings} />
        </TabsContent>
        <TabsContent value="conversations">
          <ConversationsPanel rows={conversations} />
        </TabsContent>
      </Tabs>
    </main>
  );
}
