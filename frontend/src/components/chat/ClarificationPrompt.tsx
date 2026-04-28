import { useState } from "react"
import { ShieldAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import type { ClarificationOption, ClarificationRequest } from "@/types"

interface ClarificationPromptProps {
  clarification: ClarificationRequest
  onSubmit: (option: ClarificationOption, remember: boolean) => void
}

export function ClarificationPrompt({ clarification, onSubmit }: ClarificationPromptProps) {
  const [selectedId, setSelectedId] = useState(clarification.options[0]?.id ?? "")
  const [remember, setRemember] = useState(true)

  const selected =
    clarification.options.find((option) => option.id === selectedId) ?? clarification.options[0]

  return (
    <div className="border-t border-[var(--color-base-200)] bg-[var(--color-base-50)] px-4 py-4 dark:border-[var(--color-base-800)] dark:bg-[var(--color-base-900)]">
      <div className="rounded-xl border border-[var(--color-orange-400)]/40 bg-white p-4 shadow-sm dark:bg-[var(--color-base-950)]">
        <div className="flex items-start gap-3">
          <div className="rounded-full bg-[var(--color-orange-400)]/15 p-2 text-[var(--color-orange-400)]">
            <ShieldAlert className="h-4 w-4" />
          </div>
          <div className="flex-1 space-y-3">
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-black)] dark:text-[var(--color-base-50)]">
                Privacy clarification needed
              </h3>
              <p className="mt-1 text-sm text-[var(--color-base-600)] dark:text-[var(--color-base-400)]">
                {clarification.question}
              </p>
            </div>

            <div className="rounded-md bg-[var(--color-base-100)] px-3 py-2 text-xs text-[var(--color-base-500)] dark:bg-[var(--color-base-900)] dark:text-[var(--color-base-400)]">
              <span className="font-semibold">Entity:</span> {clarification.entity}
              {clarification.reason ? ` - ${clarification.reason}` : ""}
            </div>

            <div className="space-y-2">
              {clarification.options.map((option) => (
                <label
                  key={option.id}
                  className={[
                    "flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-3 text-sm transition-colors",
                    selectedId === option.id
                      ? "border-[var(--color-blue-400)] bg-[var(--color-blue-400)]/5"
                      : "border-[var(--color-base-200)] hover:border-[var(--color-base-300)] dark:border-[var(--color-base-800)] dark:hover:border-[var(--color-base-700)]",
                  ].join(" ")}
                >
                  <input
                    type="radio"
                    name="clarification"
                    value={option.id}
                    checked={selectedId === option.id}
                    onChange={() => setSelectedId(option.id)}
                    className="mt-1"
                  />
                  <span className="text-[var(--color-black)] dark:text-[var(--color-base-100)]">
                    {option.label}
                  </span>
                </label>
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
              <Button onClick={() => selected && onSubmit(selected, remember)} disabled={!selected}>
                Continue
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
