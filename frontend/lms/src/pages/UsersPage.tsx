import UserManagementTable from "../AppComponents/Tables/UserManagementTable";

export default function UsersPage() {
  const tenant = new URLSearchParams(location.search).get("tenant") || "all";
  return <UserManagementTable tenant={tenant} />;
}
