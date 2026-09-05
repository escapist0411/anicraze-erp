import { InventoryCommandCenterV2 } from '@/components/inventory/InventoryCommandCenterV2';
import { EmployeeShopInventory } from '@/components/inventory/EmployeeShopInventory';
import { useAuth } from '@/hooks/useAuth';
export default function Inventory(){const {user}=useAuth();return user?.role==='employee'?<EmployeeShopInventory/>:<InventoryCommandCenterV2/>}
