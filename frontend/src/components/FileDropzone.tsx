import { useCallback } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";

interface FileDropzoneProps {
  onFilesAccepted: (files: File[]) => void;
  disabled?: boolean;
}

const ACCEPTED_TYPES = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
};

const MAX_SIZE_BYTES = 10 * 1024 * 1024;

export default function FileDropzone({ onFilesAccepted, disabled }: FileDropzoneProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[], rejections: FileRejection[]) => {
      if (acceptedFiles.length > 0) {
        onFilesAccepted(acceptedFiles);
      }
      if (rejections.length > 0) {
        console.warn(
          `${rejections.length} file(s) rejected — only PDF and DOCX under 10MB are supported.`
        );
      }
    },
    [onFilesAccepted]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE_BYTES,
    disabled,
    multiple: true,
  });

  return (
    <div
      {...getRootProps()}
      className={`
        border-2 border-dashed rounded-card p-12 text-center cursor-pointer
        transition-colors duration-200
        ${isDragActive ? "border-accent bg-accent/5" : "border-white/15 hover:border-white/25"}
        ${disabled ? "opacity-50 cursor-not-allowed" : ""}
      `}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-surface-raised flex items-center justify-center">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            className="text-accent"
          >
            <path
              d="M12 16V4M12 4L7 9M12 4L17 9"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M4 16V18C4 19.1046 4.89543 20 6 20H18C19.1046 20 20 19.1046 20 18V16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <p className="text-text-primary font-medium">
          {isDragActive ? "Drop resumes here" : "Drop resumes here or click to browse"}
        </p>
        <p className="text-xs text-text-secondary">
          Supports PDF and Word (.docx) files, up to 10MB each
        </p>
      </div>
    </div>
  );
}
