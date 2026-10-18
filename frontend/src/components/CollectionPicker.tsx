import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Select } from "./ui/inputs";

type Props = { value: string; onChange: (collectionId: string) => void; className?: string };

/** An empty value means "all collections". */
export function CollectionPicker({ value, onChange, className }: Props) {
  const collections = useQuery({ queryKey: ["collections"], queryFn: api.listCollections });
  return (
    <Select
      aria-label="Collection"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={className}
    >
      <option value="">All collections</option>
      {collections.data?.map((collection) => (
        <option key={collection.id} value={collection.id}>
          {collection.name}
        </option>
      ))}
    </Select>
  );
}
