import AllRulesTable from "../AppComponents/Tables/RulesTable";

export default function RulesPage() {
  const tenant = new URLSearchParams(location.search).get("tenant") || "all";
  return <AllRulesTable tenant={tenant} />;
}
