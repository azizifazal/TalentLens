import { useState } from "react";
import type { JDRequirements } from "@/types/session";

interface TraitsEditorProps {
  requirements: JDRequirements;
  onChange: (requirements: JDRequirements) => void;
}

interface TagGroupProps {
  title: string;
  items: string[];
  colorClass: string;
  onRemove: (index: number) => void;
  onAdd: (value: string) => void;
}

function TagGroup({ title, items, colorClass, onRemove, onAdd }: TagGroupProps) {
  const [inputValue, setInputValue] = useState("");

  function handleAdd() {
    const trimmed = inputValue.trim();
    if (trimmed) {
      onAdd(trimmed);
      setInputValue("");
    }
  }

  return (
    <div>
      <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
        {title}
      </h4>
      <div className="flex flex-wrap gap-2 mb-2 min-h-[28px]">
        {items.map((item, i) => (
          <span key={`${item}-${i}`} className={`tag-chip ${colorClass} group`}>
            {item}
            <button
              onClick={() => onRemove(i)}
              className="opacity-50 hover:opacity-100 transition-opacity ml-0.5"
              aria-label={`Remove ${item}`}
            >
              ×
            </button>
          </span>
        ))}
        {items.length === 0 && (
          <span className="text-xs text-muted italic">None extracted</span>
        )}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleAdd();
            }
          }}
          placeholder="Add..."
          className="input-field text-xs py-1 px-2 flex-1"
        />
        <button onClick={handleAdd} className="text-xs text-accent hover:text-accent/80">
          + Add
        </button>
      </div>
    </div>
  );
}

export default function TraitsEditor({ requirements, onChange }: TraitsEditorProps) {
  function updateField(field: keyof JDRequirements, items: string[]) {
    onChange({ ...requirements, [field]: items });
  }

  function removeAt(field: keyof JDRequirements, index: number) {
    const current = requirements[field] as string[];
    updateField(field, current.filter((_, i) => i !== index));
  }

  function addTo(field: keyof JDRequirements, value: string) {
    const current = requirements[field] as string[];
    updateField(field, [...current, value]);
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 card p-5">
      <TagGroup
        title="Required Skills"
        items={requirements.required_skills}
        colorClass="bg-accent/15 text-accent"
        onRemove={(i) => removeAt("required_skills", i)}
        onAdd={(v) => addTo("required_skills", v)}
      />
      <TagGroup
        title="Preferred Skills"
        items={requirements.preferred_skills}
        colorClass="bg-surface-raised text-text-primary"
        onRemove={(i) => removeAt("preferred_skills", i)}
        onAdd={(v) => addTo("preferred_skills", v)}
      />
      <TagGroup
        title="Success Traits"
        items={requirements.success_traits}
        colorClass="bg-behavioral/15 text-behavioral"
        onRemove={(i) => removeAt("success_traits", i)}
        onAdd={(v) => addTo("success_traits", v)}
      />
      <TagGroup
        title="Red Flags"
        items={requirements.red_flags}
        colorClass="bg-red-500/15 text-red-400"
        onRemove={(i) => removeAt("red_flags", i)}
        onAdd={(v) => addTo("red_flags", v)}
      />
      <div className="md:col-span-2 flex flex-wrap gap-4 pt-2 border-t border-white/5 text-xs text-text-secondary">
        <span>
          Role Level:{" "}
          <span className="text-text-primary font-medium">
            {requirements.role_level || "—"}
          </span>
        </span>
        <span>
          Experience:{" "}
          <span className="text-text-primary font-medium">
            {requirements.experience_min}–{requirements.experience_max} years
          </span>
        </span>
      </div>
    </div>
  );
}
