import type { ReactNode } from "react"

import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"

export function EmptyState({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children?: ReactNode
}) {
  return (
    <Empty className="min-h-[60vh] border-none">
      <EmptyHeader>
        {/* `!` on the size and weight: EmptyTitle ships `text-sm font-medium`,
            and tailwind-merge does not treat these custom tokens as the same
            groups, so without the override the DESIGN.md display token
            (28px / 650) loses to the vendored defaults and renders at 500. */}
        <EmptyTitle className="text-display! font-display! tracking-tight">
          {title}
        </EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      {children ? <EmptyContent>{children}</EmptyContent> : null}
    </Empty>
  )
}
