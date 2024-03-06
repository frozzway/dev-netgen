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


fun domainUpdate(event: AnActionEvent) {
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


fun summaryPerform(event: AnActionEvent) {
    saveAllChanges(event);
    val project = event.getProject()!!;
    val filepath = event.virtualFile!!.getPath();
    val result = runShellCommand("dev-netgen", "summary", filepath);
    show(result.stdout + result.stderr);
    refreshProject(project);
}


class CustomActionGroup: DefaultActionGroup("NetGen Group", "", AllIcons.Diff.MagicResolve) {}

class CrudAction: AnAction("Create CRUD") {

    override fun update(event: AnActionEvent) {
       domainUpdate(event)
    }

    override fun actionPerformed(event: AnActionEvent) {
        saveAllChanges(event);
        val project = event.getProject()!!;
        val filepath = event.virtualFile!!.getPath();
        val result = runShellCommand("dev-netgen", "all", filepath);
        show(result.stdout + result.stderr);
        refreshProject(project);
    }
}

class LegacyCrudAction: AnAction("Create CRUD: legacy controller") {

    override fun update(event: AnActionEvent) {
       domainUpdate(event)
    }

    override fun actionPerformed(event: AnActionEvent) {
        saveAllChanges(event);
        val project = event.getProject()!!;
        val filepath = event.virtualFile!!.getPath();
        val result = runShellCommand("dev-netgen", "all", filepath, "--legacy-controller");
        show(result.stdout + result.stderr);
        refreshProject(project);
    }
}

class ApplicationSummariesAction: AnAction("Сгенерировать <summary> - Application") {

    override fun update(event: AnActionEvent) {
       val selectedFile = event.virtualFile
       val presentation = event.presentation

       if (selectedFile != null && selectedFile.extension == "cs"
            && selectedFile.getPath().contains("Application")
            && (selectedFile.getName().endsWith("Dto.cs") || selectedFile.getName().endsWith("Vm.cs"))
          ) {
             // Делаем действие видимым и доступным
             presentation.isVisible = true
             presentation.isEnabled = true
           } else {
             // Делаем действие невидимым и недоступным
             presentation.isVisible = false
             presentation.isEnabled = false
           }
    }

    override fun actionPerformed(event: AnActionEvent) {
        summaryPerform(event)
    }
}

class DomainSummariesAction: AnAction("Сгенерировать <summary> - Domain") {
    override fun update(event: AnActionEvent) {
       domainUpdate(event)
    }

    override fun actionPerformed(event: AnActionEvent) {
        summaryPerform(event)
    }
}

val crudAction = registerAction(
    id = "Сгенерировать CRUD",
    action = CrudAction()
)

val crudLegacyAction = registerAction(
    id = "Сгенерировать CRUD: на legacy controller",
    action = LegacyCrudAction()
)

val domainSummaryAction = registerAction(
    id = "Сгенерировать <summary> в файле(-ах) Vm/Dto на основе сущности",
    action = DomainSummariesAction()
)

val applicationSummaryAction = registerAction(
    id = "Сгенерировать <summary> в файле на основе сущности",
    action = ApplicationSummariesAction()
)

val actionGroup = CustomActionGroup().also { it.isPopup = true }

actionGroup.add(crudAction)
actionGroup.add(crudLegacyAction)
actionGroup.add(domainSummaryAction)
actionGroup.add(applicationSummaryAction)


registerAction(
    id = "NetGen: генерация",
    actionGroupId = "SolutionExplorerPopupMenu",
    action = actionGroup
)