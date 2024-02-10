// Fill out your copyright notice in the Description page of Project Settings.

#pragma once
#include "CoreMinimal.h"
#include "Factories/Factory.h"
#include "Readers/UEModelReader.h"
#include "Widgets/SkelMesh/USkelMeshImportOptions.h"
#include "UEModelFactory.generated.h"

UCLASS(hidecategories=Object)
class UEFORMAT_API UEModelFactory : public UFactory
{
	GENERATED_UCLASS_BODY()

	UPROPERTY()
	USkelMeshImportOptions* SettingsImporter;
	bool bImport;
	bool bImportAll;

	static UObject* Import(const FString& Filename, const FString& PackagePath, const FName Name, const EObjectFlags Flags, TMap<FString, FString> MaterialNameToPathMap);

	virtual UObject* FactoryCreateFile(UClass* Class, UObject* Parent, FName Name, EObjectFlags Flags, const FString& Filename, const TCHAR* Params, FFeedbackContext* Warn, bool& bOutOperationCanceled) override;

	UStaticMesh* CreateStaticMesh(UEModelReader& Data, UObject* Parent, EObjectFlags Flags);

	USkeletalMesh* CreateSkeletalMeshFromStatic(UEModelReader& Data, UStaticMesh* Mesh, USkeleton* Skeleton, EObjectFlags Flags);

	USkeleton* CreateSkeleton(UPackage* ParentPackage, EObjectFlags Flags, UEModelReader& Data, FReferenceSkeleton& RefSkeleton, FSkeletalMeshImportData& SkeletalMeshImportData);
};
