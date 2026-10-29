import { Fragment, useMemo, useState, type ReactNode } from "react";
import { MessagesSquare, SearchX, Sparkles, X } from "lucide-react";
import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { CopyButton } from "@/components/arc/copy-button/copy-button";
import { EmptyState } from "@/components/arc/empty-state/empty-state";
import { SearchField } from "@/components/arc/search-field/search-field";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { SortableDataTable } from "@/components/arc/sortable-data-table/sortable-data-table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/arc/tabs/tabs";
import { data, type Conversation, type Learning } from "./data";
import styles from "./App.module.css";

const dateFormat = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });

// Dates arrive in the machine's local time: "2026-10-28" or "2026-10-28T22:31:41".
function formatDate(iso: string | null) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return Number.isNaN(date.getTime()) ? iso : dateFormat.format(date);
}

function matches(query: string, ...fields: string[]) {
  const q = query.trim().toLowerCase();
  return !q || fields.some((f) => f.toLowerCase().includes(q));
}

function plural(n: number, one: string, other: string) {
  return `${n} ${n === 1 ? one : other}`;
}

// Learnings are written as markdown; render `code` spans instead of showing backticks.
function Prose({ text }: { text: string }) {
  return (
    <>
      {text.split("`").map((part, i) =>
        i % 2 ? <code key={i} className={styles.code}>{part}</code> : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}

type LearningRow = Learning & { support: number } & Record<string, unknown>;
type ConversationRow = Conversation & { learned: number } & Record<string, unknown>;

/** A chip in the toolbar for a filter set from the other tab, with a way to clear it. */
function FilterChip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <button type="button" className={styles.chip} onClick={onClear} aria-label={`Clear filter: ${label}`}>
      {label}
      <X size={14} aria-hidden />
    </button>
  );
}

function Count({ n, one, other, onOpen }: { n: number; one: string; other: string; onOpen: () => void }) {
  if (!n) return <span className={styles.muted}>{plural(0, one, other)}</span>;
  return (
    <button type="button" className={styles.link} onClick={onOpen}>
      {plural(n, one, other)}
    </button>
  );
}

function LearningsPanel(props: {
  rows: LearningRow[];
  onlyFrom: string | null;
  clearOnlyFrom: () => void;
  openConversations: (row: LearningRow) => void;
}) {
  const { rows, onlyFrom, clearOnlyFrom, openConversations } = props;
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const visible = rows.filter(
    (r) =>
      (kind === "all" || r.type === kind) &&
      (!onlyFrom || r.conversations.includes(onlyFrom)) &&
      matches(query, r.learning, r.why, r.id),
  );
  const rules = rows.filter((r) => r.type === "rule").length;

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<Sparkles size={24} />}
        title="No learnings yet"
        description="Run /sieve in this repository to read its conversations."
      />
    );
  }

  const narrowed = query || kind !== "all" || onlyFrom;
  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <SearchField label="Search learnings" placeholder="Search learnings" value={query} onValueChange={setQuery} className={styles.search} />
        <SegmentedControl
          label="Type"
          className={styles.types}
          value={kind}
          onValueChange={setKind}
          options={[
            { value: "all", label: "All" },
            { value: "rule", label: "Rules", accessory: <span className={styles.count}>{rules}</span> },
            { value: "insight", label: "Insights", accessory: <span className={styles.count}>{rows.length - rules}</span> },
          ]}
        />
        {onlyFrom ? <FilterChip label={`From ${onlyFrom}`} onClear={clearOnlyFrom} /> : null}
      </div>
      {visible.length === 0 ? (
        <EmptyState
          icon={<SearchX size={24} />}
          title="No matches"
          description={narrowed ? "Nothing matches the search and filters." : "No learnings to show."}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                setQuery("");
                setKind("all");
                clearOnlyFrom();
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <SortableDataTable<LearningRow>
          rows={visible}
          rowKey="id"
          caption="Learnings"
          itemName={{ one: "learning", other: "learnings" }}
          defaultSort={{ key: "updated", direction: "desc" }}
          columns={[
            {
              key: "learning",
              label: "Learning",
              render: (_, row) => (
                <div className={styles.learning}>
                  <span className={styles.kind}>
                    <Badge size="sm" tone={row.type === "rule" ? "info" : "success"}>
                      {row.type === "rule" ? "Rule" : "Insight"}
                    </Badge>
                  </span>
                  <span className={styles.text}><Prose text={row.learning} /></span>
                  {row.why ? <span className={styles.why}><Prose text={row.why} /></span> : null}
                </div>
              ),
            },
            {
              key: "support",
              label: "Conversations",
              width: 156,
              render: (_, row) => (
                <Count n={row.support} one="conversation" other="conversations" onOpen={() => openConversations(row)} />
              ),
            },
            { key: "updated", label: "Updated", width: 132, render: (v) => <span className={styles.nowrap}>{formatDate(String(v))}</span> },
            { key: "id", label: "ID", width: 128, sortable: false, render: (v) => <IdCell id={String(v)} /> },
          ]}
        />
      )}
    </div>
  );
}

function IdCell({ id }: { id: string }) {
  return (
    <span className={styles.idCell}>
      <code className={styles.id}>{id}</code>
      <CopyButton value={id} label="Copy ID" iconOnly variant="plain" />
    </span>
  );
}

function ConversationsPanel(props: {
  rows: ConversationRow[];
  onlyFor: LearningRow | null;
  clearOnlyFor: () => void;
  openLearnings: (id: string) => void;
}) {
  const { rows, onlyFor, clearOnlyFor, openLearnings } = props;
  const [query, setQuery] = useState("");
  const visible = rows.filter(
    (r) => (!onlyFor || onlyFor.conversations.includes(r.conversation)) && matches(query, r.summary, r.who, r.conversation),
  );

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<MessagesSquare size={24} />}
        title="No conversations logged"
        description="Run /sieve in this repository to log its conversations."
      />
    );
  }

  const columns: { key: string; label: string; width?: number; sortable?: boolean; render?: (v: unknown, row: ConversationRow) => ReactNode }[] = [
    { key: "summary", label: "Summary", render: (v) => <span className={styles.summary}>{String(v)}</span> },
    { key: "date", label: "Date", width: 132, render: (v) => <span className={styles.nowrap}>{formatDate(String(v))}</span> },
  ];
  columns.push({ key: "who", label: "Who", width: 160 });
  columns.push(
    {
      key: "learned",
      label: "Learnings",
      width: 132,
      render: (_, row) => <Count n={row.learned} one="learning" other="learnings" onOpen={() => openLearnings(row.conversation)} />,
    },
    { key: "conversation", label: "ID", width: 128, sortable: false, render: (v) => <IdCell id={String(v)} /> },
  );

  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <SearchField label="Search conversations" placeholder="Search conversations" value={query} onValueChange={setQuery} className={styles.search} />
        {onlyFor ? <FilterChip label={`Behind ${onlyFor.id}`} onClear={clearOnlyFor} /> : null}
      </div>
      {visible.length === 0 ? (
        <EmptyState
          icon={<SearchX size={24} />}
          title="No matches"
          description={onlyFor ? "None of the conversations behind this learning match the search." : "Nothing matches the search."}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                setQuery("");
                clearOnlyFor();
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <SortableDataTable<ConversationRow>
          rows={visible}
          rowKey="conversation"
          caption="Conversations"
          itemName={{ one: "conversation", other: "conversations" }}
          defaultSort={{ key: "date", direction: "desc" }}
          columns={columns}
        />
      )}
    </div>
  );
}

export function App() {
  const learnings = useMemo<LearningRow[]>(() => data.learnings.map((l) => ({ ...l, support: l.conversations.length })), []);
  const conversations = useMemo<ConversationRow[]>(
    () =>
      data.conversations.map((c) => ({
        ...c,
        learned: data.learnings.filter((l) => l.conversations.includes(c.conversation)).length,
      })),
    [],
  );
  const [tab, setTab] = useState("learnings");
  const [learningFilter, setLearningFilter] = useState<LearningRow | null>(null);
  const [conversationFilter, setConversationFilter] = useState<string | null>(null);

  const name = data.repo.split("/").filter(Boolean).pop() ?? data.repo;
  const meta = ["Learnings shared by everyone who works on this repository with Claude Code"];

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>{name}</h1>
        <p className={styles.meta}>{meta.join(" · ")}</p>
      </header>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList aria-label="Sieve">
          <TabsTrigger value="learnings">
            Learnings <span className={styles.count}>{learnings.length}</span>
          </TabsTrigger>
          <TabsTrigger value="conversations">
            Conversations <span className={styles.count}>{conversations.length}</span>
          </TabsTrigger>
        </TabsList>
        <TabsContent value="learnings">
          <LearningsPanel
            rows={learnings}
            onlyFrom={conversationFilter}
            clearOnlyFrom={() => setConversationFilter(null)}
            openConversations={(row) => {
              setLearningFilter(row);
              setTab("conversations");
            }}
          />
        </TabsContent>
        <TabsContent value="conversations">
          <ConversationsPanel
            rows={conversations}
            onlyFor={learningFilter}
            clearOnlyFor={() => setLearningFilter(null)}
            openLearnings={(id) => {
              setConversationFilter(id);
              setTab("learnings");
            }}
          />
        </TabsContent>
      </Tabs>
    </main>
  );
}
