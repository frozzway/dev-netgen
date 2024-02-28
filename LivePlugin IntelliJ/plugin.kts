import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.Separator
import com.intellij.openapi.ui.Messages
import com.intellij.icons.AllIcons
import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.vfs.VfsUtil;
import com.intellij.openapi.project.Project;
import com.intellij.ide.actions.SaveAllAction;
import liveplugin.*


// Функция, которая вызывает действие сохранить всё
fun saveAllChanges(event: AnActionEvent) {
  // Получаем экземпляр ActionManager
  val am = ActionManager.getInstance()
  // Получаем экземпляр AnAction для действия SaveAllAction
  val saveAllAction = am.getAction("SaveAll")
  // Вызываем действие, передавая событие, контекст, место и флаги
  am.tryToExecute(saveAllAction, null, null, null, true)
}


// Функция, которая обновляет проект
fun refreshProject(project: Project) {
  // Получаем директорию проекта
  val apiDir = project.getBaseDir()
  // Вызываем метод markDirtyAndRefresh
  VfsUtil.markDirtyAndRefresh(true, true, true, apiDir)
}


class CustomDefaultActionGroup: DefaultActionGroup("NetGen Group", "", AllIcons.Diff.MagicResolve) {
  override fun update(event: AnActionEvent) {
       val selectedFile = event.virtualFile
       val presentation = event.presentation
       
       if (selectedFile != null && selectedFile.extension == "cs"
            && selectedFile.getPath().contains("Domain")) {
             // Делаем действие видимым и доступным
             presentation.isVisible = true
             presentation.isEnabled = true
           } else {
             // Делаем действие невидимым и недоступным
             presentation.isVisible = false
             presentation.isEnabled = false
           }
  }
}

class CrudAction: AnAction("Create CRUD") {

    override fun actionPerformed(event: AnActionEvent) {
        saveAllChanges(event);
        val project = event.getProject()!!;
        val filepath = event.virtualFile!!.getPath();
        val result = runShellCommand("dev-netgen", filepath);
        show(result.stdout + "\n Exit code: " + result.exitCode + result.stderr);
        refreshProject(project);
    }
}

class LegacyCrudAction: AnAction("Create CRUD: legacy controller") {

    override fun actionPerformed(event: AnActionEvent) {
        saveAllChanges(event);
        val project = event.getProject()!!;
        val filepath = event.virtualFile!!.getPath();
        val result = runShellCommand("dev-netgen", filepath, "--legacy-controller");
        show(result.stdout + "\n Exit code: " + result.exitCode + result.stderr);
        refreshProject(project);
    }
}

val crudAction = registerAction(
    id = "Create CRUD",
    action = CrudAction()
)

val crudLegacyAction = registerAction(
    id = "Create CRUD: legacy controller",
    action = LegacyCrudAction()
)

val actionGroup = CustomDefaultActionGroup().also { it.isPopup = true }

actionGroup.add(crudAction)
actionGroup.add(crudLegacyAction)

registerAction(
    id = "NetGen: CRUD",
    actionGroupId = "SolutionExplorerPopupMenu",
    action = actionGroup
)