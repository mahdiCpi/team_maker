import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { BuildResultView } from "@/lib/api-types"

/**
 * The build outcome, reported **on this surface** (AC 5).
 *
 * `EXPERIENCE.md:186` describes the team landing in My Teams and the user being
 * dropped into its workspace. Neither surface exists until Stories 2.5 and 2.4,
 * so navigating there would send the user somewhere that cannot show any of
 * this. The outcome is reported inline instead, and the destination is not faked.
 *
 * `model_substitutions` is rendered unconditionally when non-empty and stated in
 * plain language: `normalize_team_routings` can silently swap a chosen model for
 * a fuzzy nearest match and reports it only to stderr, so without this the UI
 * would claim it built the model the user asked for.
 *
 * `output_path` is text and nothing else — not a link, not an input, not an
 * input's default. It is an absolute path on the *server's* filesystem, chosen
 * by the server and pinned for the session (Story 2.0 AC 13).
 */
export function BuildResult({ result }: { result: BuildResultView }) {
  const { validation } = result

  return (
    <Card data-slot="build-result" className="mb-3">
      <CardHeader>
        <CardTitle data-slot="build-result-name">{result.team_name}</CardTitle>
        <CardDescription>
          Built {result.agent_count}{" "}
          {result.agent_count === 1 ? "agent" : "agents"} and{" "}
          {result.task_count} {result.task_count === 1 ? "task" : "tasks"} across{" "}
          {result.written_file_count} files.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <div>
          <p className="text-xs text-muted-foreground">Written to</p>
          <p
            data-slot="build-output-path"
            className="font-mono text-xs break-all"
          >
            {result.output_path}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            This location is chosen by the server, on the machine running
            team_maker.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Validation</span>
          {/* Tri-state. `passed === null` means the server sent no usable verdict;
              rendering that as "Failed" claimed a failure the response never
              made, on a build that had just written files to disk. */}
          <Badge
            data-slot="build-validation"
            variant={
              validation.passed === null
                ? "outline"
                : validation.passed
                  ? "secondary"
                  : "destructive"
            }
          >
            {validation.passed === null
              ? "Not reported"
              : validation.passed
                ? "Passed"
                : "Failed"}
          </Badge>
        </div>

        {validation.issues.length > 0 ? (
          <IssueList
            slot="build-validation-issues"
            heading="Issues"
            items={validation.issues}
          />
        ) : null}
        {validation.warnings.length > 0 ? (
          <IssueList
            slot="build-validation-warnings"
            heading="Warnings"
            items={validation.warnings}
          />
        ) : null}

        {result.model_substitutions.length > 0 ? (
          <div data-slot="build-substitutions">
            <p className="text-xs text-muted-foreground">
              {result.model_substitutions.length === 1
                ? "One model was not available and a near match was used instead."
                : "Some models were not available and near matches were used instead."}
            </p>
            <ul className="mt-1 flex flex-col gap-1">
              {result.model_substitutions.map((substitution) => (
                <li
                  key={`${substitution.role}-${substitution.requested}`}
                  data-slot="build-substitution"
                  className="text-xs"
                >
                  <span className="font-medium">{substitution.role}</span>:{" "}
                  <span className="font-mono">{substitution.requested}</span> →{" "}
                  <span className="font-mono">{substitution.resolved}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function IssueList({
  slot,
  heading,
  items,
}: {
  slot: string
  heading: string
  items: string[]
}) {
  return (
    <div data-slot={slot}>
      <p className="text-xs text-muted-foreground">{heading}</p>
      <ul className="mt-1 flex flex-col gap-1">
        {items.map((item) => (
          <li key={item} className="text-xs">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
