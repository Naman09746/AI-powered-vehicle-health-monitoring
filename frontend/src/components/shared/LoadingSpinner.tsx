export function LoadingSpinner({ size = "md", label }: { size?: "sm" | "md" | "lg"; label?: string }) {
  const sizes = { sm: "w-4 h-4", md: "w-8 h-8", lg: "w-12 h-12" };
  return (
    <div className="flex items-center justify-center p-8" role="status" aria-label={label ?? "Loading"}>
      <div
        className={`${sizes[size]} border-2 border-border border-t-accent-sky rounded-full animate-spin`}
        aria-hidden="true"
      />
      {label && <span className="sr-only">{label}</span>}
    </div>
  );
}
