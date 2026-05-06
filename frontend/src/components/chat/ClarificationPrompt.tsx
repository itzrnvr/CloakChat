import { useState } from "react"
import { ShieldQuestion } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import type { ClarificationItem, ClarificationRequest, ClarificationSelection } from "@/types"

interface ClarificationPromptProps {
  clarification: ClarificationRequest
  onSubmit: (answers: ClarificationSelection[], remember: boolean) => void
}

export function ClarificationPrompt({ clarification, onSubmit }: ClarificationPromptProps) {
  const items = clarification.items?.length ? clarification.items : [clarification]
  const [selectedIds, setSelectedIds] = useState<Record<string, string>>(() =>
    Object.fromEntries(items.map((item, index) => [String(index), item.options[0]?.id ?? ""]))
  )
  const [remember, setRemember] = useState(true)

  const selections = items
    .map((item, index) => ({
      item,
      option: item.options.find((option) => option.id === selectedIds[String(index)]),
    }))
    .filter((selection): selection is ClarificationSelection => Boolean(selection.option))
  const canContinue = selections.length === items.length

  return (
    <div className="border-t border-[var(--color-base-200)] bg-[var(--color-base-50)] px-4 py-4 dark:border-[var(--color-base-800)] dark:bg-[var(--color-base-900)]">
      <div className="rounded-lg border border-[var(--color-orange-400)]/40 bg-white p-4 shadow-sm dark:bg-[var(--color-base-950)]">
        <div className="flex items-start gap-3">
          <div className="rounded-full bg-[var(--color-orange-400)]/15 p-2 text-[var(--color-orange-400)]">
            <ShieldQuestion className="h-4 w-4" />
          </div>
          <div className="flex-1 space-y-3">
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-black)] dark:text-[var(--color-base-50)]">
                {items.length > 1 ? "Clarifications needed" : "Clarification needed"}
              </h3>
            </div>

            <div className="space-y-3">
              {items.map((item, itemIndex) => (
                <ClarificationChoice
                  key={`${item.entityType}:${item.entity}:${itemIndex}`}
                  item={item}
                  itemIndex={itemIndex}
                  selectedId={selectedIds[String(itemIndex)] ?? ""}
                  onSelect={(optionId) =>
                    setSelectedIds((current) => ({ ...current, [String(itemIndex)]: optionId }))
                  }
                />
              ))}
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="remember-clarification"
                checked={remember}
                onCheckedChange={(checked) => setRemember(Boolean(checked))}
              />
              <label
                htmlFor="remember-clarification"
                className="cursor-pointer text-sm text-[var(--color-base-600)] dark:text-[var(--color-base-400)]"
              >
                Remember this choice in the playbook
              </label>
            </div>

            <div className="flex justify-end">
              <Button onClick={() => onSubmit(selections, remember)} disabled={!canContinue}>
                Continue
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

interface ClarificationChoiceProps {
  item: ClarificationItem
  itemIndex: number
  selectedId: string
  onSelect: (optionId: string) => void
}

function ClarificationChoice({ item, itemIndex, selectedId, onSelect }: ClarificationChoiceProps) {
  return (
    <div className="rounded-lg border border-[var(--color-base-200)] p-3 dark:border-[var(--color-base-800)]">
      <p className="text-sm text-[var(--color-base-700)] dark:text-[var(--color-base-300)]">
        {item.question}
      </p>
      {item.reason ? (
        <p className="mt-1 text-xs text-[var(--color-base-500)] dark:text-[var(--color-base-400)]">
          {item.reason}
        </p>
      ) : null}

      <div className="mt-3 space-y-2">
        {item.options.map((option) => (
          <label
            key={option.id}
            className={[
              "flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2 text-sm transition-colors",
              selectedId === option.id
                ? "border-[var(--color-blue-400)] bg-[var(--color-blue-400)]/5"
                : "border-[var(--color-base-200)] hover:border-[var(--color-base-300)] dark:border-[var(--color-base-800)] dark:hover:border-[var(--color-base-700)]",
            ].join(" ")}
          >
            <input
              type="radio"
              name={`clarification-${itemIndex}`}
              value={option.id}
              checked={selectedId === option.id}
              onChange={() => onSelect(option.id)}
              className="mt-1"
            />
            <span className="text-[var(--color-black)] dark:text-[var(--color-base-100)]">
              {option.label}
            </span>
          </label>
        ))}
      </div>
    </div>
  )
}
